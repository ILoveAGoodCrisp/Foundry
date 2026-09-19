

from math import radians
from typing import cast

from mathutils import Matrix, Vector, Color



from ..tools.property_apply import apply_props_material

from ..props.object import NWO_ObjectPropertiesGroup
from ..props.light import NWO_LightPropertiesGroup
from ..tags.blender import BlenderTag
from ..tags.backend import TagDocument
import struct
import math
from . import import_transform
from .. import utils
import bpy

class ScenarioStructureLightingInfoTag(BlenderTag, TagDocument):
    tag_ext = 'scenario_structure_lighting_info'


    def __init__(self, path='', **kwargs):
        kwargs.setdefault('tag_must_exist', False)
        super().__init__(path, **kwargs)
        if self.valid:
            self._read_fields()

    @staticmethod
    def _add(block):
        return block[block.add()]

    @staticmethod
    def _reference_path(reference):
        return reference.RelativePathWithExtension if reference else ''

    def _data(self, element, name):
        value = self.value(element, name)
        if hasattr(value, 'to_array'):
            value = tuple(value.to_array())
        elif hasattr(value, 'red'):
            value = (value.red, value.green, value.blue)
        elif hasattr(value, 'lower'):
            value = (value.lower, value.upper)
        numbers = value if isinstance(value, tuple) else (value,)
        if any(isinstance(v, (float, int)) and not math.isfinite(v) for v in numbers):
            raise ValueError(f'{self.path}: non-finite {name}')
        return value

    def _index(self, element, name):
        field = self.required_field(element, name)
        options = field.options()
        if options is None:
            return field.value
        if options.current is None or not 0 <= options.current < len(options.names):
            raise ValueError(f'{self.path}: unknown {name} enum')
        return options.current

    def _set(self, element, name, value):
        field = self.required_field(element, name)
        if isinstance(value, (list, tuple, Vector, Color)):
            if not all(math.isfinite(v) for v in value):
                raise ValueError(f'{self.path}: non-finite {name}')
            value = type(field.value)(*value)
        elif isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f'{self.path}: non-finite {name}')
        field.set(value)

    def _mapping_data(self, mapping):
        return self.required_field(mapping.as_struct(), 'data')

    def _mapping_min(self, mapping):
        from blam_tags import TagFunctionEditor
        description = TagFunctionEditor(self._mapping_data(mapping).value).describe()
        if description['master_type'] != 0 or description['is_ranged'] or description['colors']:
            raise NotImplementedError(f'{self.path}: animated lighting-info functions are not implemented')
        value = description['clamp'][0]
        if not math.isfinite(value):
            raise ValueError(f'{self.path}: non-finite light function')
        return value

    def _set_mapping_min(self, mapping, value, initialize=False):
        if not math.isfinite(value):
            raise ValueError(f'{self.path}: non-finite light function')
        field = self._mapping_data(mapping)
        if field.value and not initialize:
            self._mapping_min(mapping)
            payload = bytearray(field.value)
        else:
            payload = bytearray(32)
            payload[0] = 1  # Native scalar constant function.
        struct.pack_into('<f', payload, 4, value)
        field.set(bytes(payload))

    def _preflight_import(self):
        if not self.corinth:
            for element in self.block_generic_light_instances:
                if element.field('gel reference') is None:
                    raise NotImplementedError(f'{self.path}: older lighting-info instance layout is not implemented')
        for element in self.block_generic_light_definitions:
            parameters = self.required_field(element, 'Midnight_Light_Parameters').as_struct() if self.corinth else element
            kind = self._index(parameters, 'Light Type' if self.corinth else 'type')
            if kind not in range(3):
                raise NotImplementedError(f'{self.path}: light type {kind} has no Blender mapping')
            if self.corinth:
                for name in ('Intensity', 'Distance Attenuation End', 'Outer Cone End') if kind == 1 else ('Intensity', 'Distance Attenuation End'):
                    function = self.required_field(parameters, name).as_struct()
                    if any(self.value(function, n).strip() for n in ('Input Variable', 'Range Variable', 'Output Modifier Input')):
                        raise NotImplementedError(f'{self.path}: driven lighting-info functions are not implemented')
                    self._mapping_min(self.required_field(function, 'Mapping'))
                gobo = self.reference(parameters, 'Gobo Tag Path')
                if self.path_exists(gobo):
                    raise NotImplementedError(f'{self.path}: native lighting-info gobo bitmap conversion is not implemented')
        for element in self.block_generic_light_instances:
            index = self.value(element, 'Light Definition Index' if self.corinth else 'definition index')
            if not 0 <= index < len(self.block_generic_light_definitions):
                raise ValueError(f'{self.path}: invalid light definition index {index}')
            self._data(element, 'origin')
            forward, up = Vector(self._data(element, 'forward')), Vector(self._data(element, 'up'))
            if forward.cross(up).length_squared == 0:
                raise ValueError(f'{self.path}: degenerate light orientation')
            if not self.corinth and self.path_exists(self.reference(element, 'gel reference')):
                raise NotImplementedError(f'{self.path}: native lighting-info gobo bitmap conversion is not implemented')

    def _read_fields(self):
        self.block_generic_light_definitions = self.block(self.tag.root(), 'generic light definitions')
        self.block_generic_light_instances = self.block(self.tag.root(), 'generic light instances')

    def _definition_index_from_id(self, id) -> int:
        for element_index, element in enumerate(self.block_generic_light_definitions):
            if id == self.value(element, 'Definition Identifier'):
                return element_index

        raise ValueError(f'Unknown light definition ID {id}')

    def _definition_index_from_data_name(self, name, light_definitions) -> int:
        for definition in light_definitions:
            if name == definition.data_name:
                return definition.index

        raise ValueError(f'Unknown light definition {name!r}')

    def clear_lights(self):
        self.block_generic_light_definitions.clear()
        self.block_generic_light_instances.clear()
        if self.corinth:
            self.block(self.tag.root(), 'cinematic light instances').clear()
        self.tag_has_changes = True

    def build_tag(self, light_instances, light_definitions):
        names = [light.data_name for light in light_definitions]
        if len(set(names)) != len(names):
            raise ValueError('Light definition names must be unique')
        if any(light.data_name not in names for light in light_instances):
            raise ValueError('Light instance references an unknown definition')
        if self.corinth and len(self.block(self.tag.root(), 'cinematic light instances')):
            raise NotImplementedError('Updating cinematic light links during lighting-info export is not implemented')
        if self.corinth:
            self._write_corinth_light_definitions(light_definitions)
            self._write_corinth_light_instances(light_instances, light_definitions)
        else:
            self.block_generic_light_definitions.clear()
            for _ in range(len(light_definitions)):
                self._add(self.block_generic_light_definitions)
            self.block_generic_light_instances.clear()
            for _ in range(len(light_instances)):
                self._add(self.block_generic_light_instances)

            self._write_reach_light_definitions(light_definitions)
            self._write_reach_light_instances(light_instances, light_definitions)

        self.tag_has_changes = True

    def _write_corinth_light_definitions(self, light_definitions):
        remaining_light_indices = list(range(len(light_definitions)))
        remove_indices = []

        for element_index, element in enumerate(self.block_generic_light_definitions):
            element_id = self.value(element, 'Definition Identifier')
            found_light = next((light for light in light_definitions if light.id == element_id), None)
            if found_light is None:
                remove_indices.append(element_index)
            else:
                remaining_light_indices.remove(light_definitions.index(found_light))
                self._update_corinth_light_definitions(found_light, element)

        if remove_indices:
            for i in reversed(remove_indices):
                self.block_generic_light_definitions.delete(i)

        for i in remaining_light_indices:
            self._update_corinth_light_definitions(light_definitions[i], self._add(self.block_generic_light_definitions), initialize=True)

    def _update_corinth_light_definitions(self, light, element, initialize=False):
        self._set(element, 'Definition Identifier', light.id )
        parameters_struct  = self.required_field(element, 'Midnight_Light_Parameters')
        parameters = parameters_struct.as_struct()
        initialize_cone = initialize or self._index(parameters, 'Light Type') != 1
        self._set(parameters, 'haloLightNode', light.data_name)
        self._set(parameters, 'Light Type', light.type)
        self._set(parameters, 'Light Color', light.color)
        intensity_struct = self.required_field(parameters, 'Intensity')
        intensity = intensity_struct.as_struct()
        intensity_mapping = self.required_field(intensity, 'Mapping')
        self._set_mapping_min(intensity_mapping, light.intensity, initialize)
        self._set(parameters, 'Lighting Mode', light.lighting_mode)
        self._set(parameters, 'Distance Attenuation Start', light.far_attenuation_start)
        atten_struct = self.required_field(parameters, 'Distance Attenuation End')
        atten = atten_struct.as_struct()
        atten_mapping = self.required_field(atten, 'Mapping')
        self._set_mapping_min(atten_mapping, light.far_attenuation_end, initialize)

        if light.type == 1: # Spot
            self._set(parameters, 'Inner Cone Angle', light.hotspot_size)
            hotpot_struct = self.required_field(parameters, 'Outer Cone End')
            hotspot = hotpot_struct.as_struct()
            hotspot_mapping = self.required_field(hotspot, 'Mapping')
            self._set_mapping_min(hotspot_mapping, light.hotspot_cutoff, initialize_cone)
            self._set(parameters, 'Cone Projection Shape', light.cone_shape)

        if light.is_sun: # Sun
            self._set(element, 'sun', 1)
        else:
            self._set(element, 'sun', 0)

        # Dynamic Only
        self._set(parameters, 'Shadow Near Clip Plane', light.shadow_near_clip)
        self._set(parameters, 'Shadow Far Clip Plane', light.shadow_far_clip)
        self._set(parameters, 'Shadow Bias Offset', light.shadow_bias)
        self._set(parameters, 'Dynamic Shadow Quality', light.shadow_quality)
        self._set(parameters, 'Shadows', light.shadows)
        self._set(parameters, 'Screenspace Light', light.screen_space)
        self._set(parameters, 'Ignore Dynamic Objects', light.ignore_dynamic_objects)
        self._set(parameters, 'Cinema Objects Only', light.cinema_objects_only)
        self._set(parameters, 'Cinema Only', light.cinema_only)
        self._set(parameters, 'Cinema Exclude', light.cinema_exclude)
        self._set(parameters, 'Specular Contribution', light.specular_contribution)
        self._set(parameters, 'Diffuse Contribution', light.diffuse_contribution)
        # Static Only
        self._set(element, 'indirect amplification factor', light.indirect_amp)
        self._set(element, 'jitter sphere radius', light.jitter_sphere)
        self._set(element, 'jitter angle', light.jitter_angle)
        self._set(element, 'jitter quality', light.jitter_quality)
        self._set(element, 'indirect only', light.indirect_only)
        self._set(element, 'static analytic', light.static_analytic)


    def _write_corinth_light_instances(self, light_instances, light_definitions):
        self.block_generic_light_instances.clear()
        for light in light_instances:
            element = self._add(self.block_generic_light_instances)
            id = utils.id_from_string(light.data_name)
            self._set(element, 'Light Definition ID', id)
            self._set(element, 'Light Definition Index', self._definition_index_from_id(id))
            self._set(element, 'light mode', light.light_mode)
            self._set(element, 'origin', light.origin)
            self._set(element, 'forward', light.forward)
            self._set(element, 'up', light.up)

    def _write_reach_light_definitions(self, light_definitions):
        for idx, light in enumerate(light_definitions):
            element = self.block_generic_light_definitions[idx]
            light.index = idx
            self._set(element, 'type', light.type)
            self._set(element, 'shape', light.shape)
            self._set(element, 'color', light.color)
            self._set(element, 'intensity', light.intensity)

            if light.type == 1:
                self._set(element, 'hotspot size', light.hotspot_size)
                self._set(element, 'hotspot cutoff size', light.hotspot_cutoff)
                self._set(element, 'hotspot falloff speed', light.hotspot_falloff)

            self._set(element, 'near attenuation bounds', [light.near_attenuation_start, light.near_attenuation_end])

            flags = self.required_field(element, 'flags')
            flags.set_flag("use far attenuation", True)
            self._set(element, 'far attenuation bounds', [light.far_attenuation_start, light.far_attenuation_end])
            flags.set_flag("invere squared falloff", light.inverse_squared_falloff)

            self._set(element, 'aspect', light.aspect)

    def _write_reach_light_instances(self, light_instances, light_definitions):
        for idx, light in enumerate(light_instances):
            element = self.block_generic_light_instances[idx]
            self._set(element, 'definition index', self._definition_index_from_data_name(light.data_name, light_definitions))
            self._set(element, 'origin', light.origin)
            self._set(element, 'forward', light.forward)
            self._set(element, 'up', light.up)
            self._set(element, 'bungie light type', light.game_type)

            flags = self.required_field(element, 'screen space specular')
            flags.set_flag("screen space light has specular", light.screen_space_specular)

            self._set(element, 'bounce light control', light.bounce_ratio)

            self._set(element, 'light volume distance', light.volume_distance)
            self._set(element, 'light volume intensity scalar', light.volume_intensity)
            self._set(element, 'fade out distance', light.fade_out_distance)
            self._set(element, 'fade start distance', light.fade_start_distance)

            if light.light_tag:
                self.set_reference(element, 'user control', light.light_tag)
            if light.shader:
                self.set_reference(element, 'shader reference', light.shader)
            if light.gel:
                self.set_reference(element, 'gel reference', light.gel)
            if light.lens_flare:
                self.set_reference(element, 'lens flare reference', light.lens_flare)

    def lightmap_regions_to_blender(self, parent_collection=None):
        if self.corinth:
            return []
        records = []
        for region in self.block(self.tag.root(), 'regions'):
            vertices = [self._data(tri, f'v{i}') for tri in self.block(region, 'triangles') for i in range(3)]
            if vertices:
                records.append((self.value(region, 'name'), vertices))
        objects = []
        for name, vertices in records:
            mesh = bpy.data.meshes.new(name)
            mesh.from_pydata([Vector(v) * 100 for v in vertices], [],
                             [list(range(i, i+3)) for i in range(0, len(vertices), 3)])
            mesh.transform(import_transform.mesh_matrix())
            mesh.nwo.mesh_type = '_connected_geometry_mesh_type_lightmap_region'
            ob = bpy.data.objects.new(name, mesh)
            ob.matrix_world = import_transform.rotation_matrix()
            apply_props_material(ob, 'LightmapRegion')
            objects.append(ob)
        if objects:
            collection = bpy.data.collections.new(f'{self.tag_path.ShortName}_lightmap_regions')
            (parent_collection or bpy.context.scene.collection).children.link(collection)
            for ob in objects:
                collection.objects.link(ob)
        return objects

    def lightmap_regions_from_blender(self, region_objects):
        if self.corinth:
            return
        # Collect geometry before changing the tag and always release temporary meshes.
        records = []
        for proxy in region_objects:
            mesh = proxy.ob.to_mesh()
            try:
                mesh.transform(utils.halo_transforms(proxy))
                mesh.calc_loop_triangles()
                vertices = [tuple(mesh.vertices[mesh.loops[i].vertex_index].co)
                            for tri in mesh.loop_triangles for i in tri.loops]
                if not all(math.isfinite(v) for point in vertices for v in point):
                    raise ValueError('Lightmap region contains non-finite vertices')
                if vertices:
                    records.append((proxy.name.lower(), vertices))
            finally:
                proxy.ob.to_mesh_clear()
        regions = self.block(self.tag.root(), 'regions')
        regions.clear()
        for name, vertices in records:
            region = self._add(regions)
            self._set(region, 'name', name)
            triangles = self.block(region, 'triangles')
            for start in range(0, len(vertices), 3):
                triangle = self._add(triangles)
                for i in range(3):
                    self._set(triangle, f'v{i}', vertices[start+i])
        self.tag_has_changes = True

    def to_blender(self, parent_collection: bpy.types.Collection = None, cinematic_cameras: list[bpy.types.Object] = []):
        self._preflight_import()
        self.camera_lights = {c: set() for c in cinematic_cameras}
        if self.corinth:
            definitions = self._from_corinth_light_definitions()
            objects = self._from_corinth_light_instances(definitions, cinematic_cameras)
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

    def _from_corinth_light_instances(self, definitions: dict[int: bpy.types.Light], cinematic_cameras: list[bpy.types.Object]):
        objects = []

        def decode_shot_flags(value, base_shot=1):
            shots = []
            bit = 0
            while value:
                if value & 1:
                    shots.append(base_shot + bit)
                value >>= 1
                bit += 1
            return shots

        ob_indices = {}
        for element_index, element in enumerate(self.block_generic_light_instances):
            def_index = self._data(element, 'Light Definition Index')
            blender_light = definitions.get(def_index)
            if blender_light is None:
                continue

            ob = cast(bpy.types.Object, bpy.data.objects.new(blender_light.name, blender_light))
            nwo = cast(NWO_ObjectPropertiesGroup, ob.nwo)

            origin = Vector(*(self._data(element, 'origin'),)) * 100
            forward = Vector((*self._data(element, 'forward'),)).normalized()
            up = Vector((*self._data(element, 'up'),)).normalized()
            left = up.cross(forward).normalized()

            matrix = Matrix((
                (forward[0], left[0], up[0], origin[0]),
                (forward[1], left[1], up[1], origin[1]),
                (forward[2], left[2], up[2], origin[2]),
                (0, 0, 0, 1),
            ))

            ob.matrix_world = import_transform.transform_matrix(matrix)
            ob.scale *= (1 / 0.03048)

            match self._index(element, 'light mode'):
                case 0:
                    nwo.light_mode = '_connected_geometry_light_mode_dynamic'
                case 1:
                    nwo.light_mode = '_connected_geometry_light_mode_static'
                case 2:
                    nwo.light_mode = '_connected_geometry_light_mode_analytic'

            objects.append(ob)
            ob_indices[element_index] = ob

            if cinematic_cameras:
                nwo.is_cinematic_light = True

        if cinematic_cameras:
            for element in self.block(self.tag.root(), 'cinematic light instances'):
                instance_index = self.value(element, 'Light Instance Index')
                if instance_index >= 0:
                    ob = ob_indices.get(instance_index)
                    if ob is None:
                        continue

                    shots = []
                    for chunk_index, chunk in enumerate(self.required_field(element, 'Active Shots').as_array()):
                        shots += decode_shot_flags(self.value(chunk, 'shot flag data') & 0xffffffff,
                                                   base_shot=1 + 32 * chunk_index)
                    for idx, camera in enumerate(cinematic_cameras):
                        shot_index = idx + 1
                        if shot_index in shots:
                            self.camera_lights[camera].add(ob)

        return objects

    def _from_corinth_light_definitions(self):
        definitions: dict[int: bpy.types.Light] = {}
        for element_index, element in enumerate(self.block_generic_light_definitions):
            parameters = self.required_field(element, 'Midnight_Light_Parameters').as_struct()
            name = self.value(parameters, 'haloLightNode')
            match self._index(parameters, 'Light Type'):
                case 0:
                    blender_light = cast(bpy.types.Light, bpy.data.lights.new(name, 'POINT'))
                case 1:
                    blender_light = cast(bpy.types.Light, bpy.data.lights.new(name, 'SPOT'))
                    inner_cone = self._data(parameters, 'Inner Cone Angle')
                    hotpot_struct = self.required_field(parameters, 'Outer Cone End')
                    hotspot = hotpot_struct.as_struct()
                    hotspot_mapping = self.required_field(hotspot, 'Mapping')
                    outer_cone = self._mapping_min(hotspot_mapping)
                    blender_light.spot_size = radians(outer_cone)
                    if outer_cone > 0.0:
                        blender_light.spot_blend = 1 - inner_cone / outer_cone
                case 2:
                    blender_light = cast(bpy.types.Light, bpy.data.lights.new(name, 'SUN'))

            nwo = cast(NWO_LightPropertiesGroup, blender_light.nwo)

            blender_light.color = [utils.srgb_to_linear(c) for c in self._data(parameters, 'Light Color')]

            intensity_struct = self.required_field(parameters, 'Intensity')
            intensity = intensity_struct.as_struct()
            intensity_mapping = self.required_field(intensity, 'Mapping')

            blender_light.nwo.light_intensity = self._mapping_min(intensity_mapping)

            nwo.light_physically_correct = self._index(parameters, 'Lighting Mode') == 0

            nwo.light_far_attenuation_start = import_transform.distance(self._data(parameters, 'Distance Attenuation Start'))
            atten_struct = self.required_field(parameters, 'Distance Attenuation End')
            atten = atten_struct.as_struct()
            atten_mapping = self.required_field(atten, 'Mapping')

            nwo.light_far_attenuation_end = import_transform.distance(self._mapping_min(atten_mapping))

            nwo.light_cone_projection_shape = '_connected_geometry_cone_projection_shape_cone' if self._index(parameters, 'Cone Projection Shape') == 0 else '_connected_geometry_cone_projection_shape_frustum'

            # Dynamic props

            nwo.light_shadow_near_clipplane = self._data(parameters, 'Shadow Near Clip Plane')
            nwo.light_shadow_far_clipplane = self._data(parameters, 'Shadow Far Clip Plane')
            nwo.light_shadow_bias_offset = self._data(parameters, 'Shadow Bias Offset')
            nwo.light_dynamic_shadow_quality = '_connected_geometry_dynamic_shadow_quality_normal' if self._index(parameters, 'Dynamic Shadow Quality') == 0 else '_connected_geometry_dynamic_shadow_quality_expensive'
            nwo.light_shadows = self._index(parameters, 'Shadows') == 1
            nwo.light_screenspace = self._index(parameters, 'Screenspace Light') == 1
            nwo.light_ignore_dynamic_objects = self._index(parameters, 'Ignore Dynamic Objects') == 1
            nwo.light_cinema_objects_only = self._index(parameters, 'Cinema Objects Only') == 1
            if self._index(parameters, 'Cinema Only') == 1:
                nwo.light_cinema = '_connected_geometry_lighting_cinema_only'
            if self._index(parameters, 'Cinema Exclude') == 1:
                nwo.light_cinema = '_connected_geometry_lighting_cinema_exclude'

            nwo.light_specular_contribution = self._index(parameters, 'Specular Contribution') == 1
            nwo.light_diffuse_contribution = self._index(parameters, 'Diffuse Contribution') == 1

            # Static Props

            nwo.light_amplification_factor = self._data(element, 'indirect amplification factor')
            blender_light.shadow_soft_size = self._data(element, 'jitter sphere radius') * import_transform.scale_factor()
            nwo.light_jitter_angle = radians(self._data(element, 'jitter angle'))

            match self._index(element, 'jitter quality'):
                case 0:
                    nwo.light_jitter_quality = '_connected_geometry_light_jitter_quality_low'
                case 1:
                    nwo.light_jitter_quality = '_connected_geometry_light_jitter_quality_medium'
                case 2:
                    nwo.light_jitter_quality = '_connected_geometry_light_jitter_quality_high'

            nwo.is_sun = self._index(element, 'sun') == 1
            nwo.light_indirect_only = self._index(element, 'indirect only') == 1
            nwo.light_static_analytic = self._index(element, 'static analytic') == 1

            definitions[element_index] = blender_light

            if blender_light.type == 'SUN':
                blender_light.energy = blender_light.nwo.light_intensity
            elif nwo.light_physically_correct:
                blender_light.energy = blender_light.nwo.light_intensity * (utils.get_import_scale(bpy.context) ** 2)
            else:
                utils.make_halo_light(blender_light)

        return definitions

    def _from_reach_light_instances(self, definitions: dict[int: bpy.types.Light]):
        objects = []
        for element_index, element in enumerate(self.block_generic_light_instances):
            blender_light = definitions.get(self._data(element, 'definition index'))
            if blender_light is None:
                continue

            ob = cast(bpy.types.Object, bpy.data.objects.new(f"light_instance:{element_index}", blender_light))
            nwo = cast(NWO_ObjectPropertiesGroup, ob.nwo)

            origin = Vector(*(self._data(element, 'origin'),)) * 100
            forward = Vector((*self._data(element, 'forward'),)).normalized()
            up = Vector((*self._data(element, 'up'),)).normalized()
            left = up.cross(forward).normalized()

            matrix = Matrix((
                (forward[0], left[0], up[0], origin[0]),
                (forward[1], left[1], up[1], origin[1]),
                (forward[2], left[2], up[2], origin[2]),
                (0, 0, 0, 1),
            ))

            ob.matrix_world = import_transform.transform_matrix(matrix)
            ob.scale *= (1 / 0.03048)

            match self._index(element, 'bungie light type'):
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

            nwo.light_screenspace_has_specular = self.required_field(element, 'screen space specular').get_flag("screen space light has specular")
            nwo.light_bounce_ratio = self._data(element, 'bounce light control')
            nwo.light_volume_distance = self._data(element, 'light volume distance') * import_transform.scale_factor()
            nwo.light_volume_intensity = self._data(element, 'light volume intensity scalar')
            nwo.light_fade_end_distance = self._data(element, 'fade out distance') * import_transform.scale_factor()
            nwo.light_fade_start_distance = self._data(element, 'fade start distance') * import_transform.scale_factor()
            nwo.light_tag_override = self._reference_path(self.reference(element, 'user control'))
            nwo.light_shader_reference = self._reference_path(self.reference(element, 'shader reference'))
            gobo_tag_path = self.reference(element, 'gel reference')
            nwo.light_gel_reference = self._reference_path(gobo_tag_path)
            nwo.light_lens_flare_reference = self._reference_path(self.reference(element, 'lens flare reference'))

            if not blender_light.use_custom_distance:
                if blender_light in self.inverse_squared_lights:
                    blender_light.energy = utils.calc_light_energy(blender_light, blender_light.nwo.light_intensity, 1)
                else:
                    gobo_image = None
                    if self.path_exists(gobo_tag_path):
                        raise NotImplementedError('Native lighting-info gobo bitmap conversion is not implemented')

                    utils.make_halo_light(blender_light, gobo_image=gobo_image)

            objects.append(ob)

        return objects

    def _from_reach_light_definitions(self):
        self.inverse_squared_lights = set()
        definitions: dict[int: bpy.types.Light] = {}
        for element_index, element in enumerate(self.block_generic_light_definitions):
            match self._index(element, 'type'):
                case 0:
                    blender_light = cast(bpy.types.Light, bpy.data.lights.new(f"light_definition:{element_index}", 'POINT'))
                case 1:
                    blender_light = cast(bpy.types.Light, bpy.data.lights.new(f"light_definition:{element_index}", 'SPOT'))
                    hotspot_cutoff_size = self._data(element, 'hotspot cutoff size')
                    blender_light.spot_size = radians(hotspot_cutoff_size)
                    if hotspot_cutoff_size > 0.0:
                        blender_light.spot_blend = 1 - self._data(element, 'hotspot size') / hotspot_cutoff_size
                case 2:
                    blender_light = cast(bpy.types.Light, bpy.data.lights.new(f"light_definition:{element_index}", 'SUN'))

            nwo = cast(NWO_LightPropertiesGroup, blender_light.nwo)

            nwo.light_shape = '_connected_geometry_light_shape_circle' if self._index(element, 'shape') == 1 else '_connected_geometry_light_shape_rectangle'
            blender_light.color = [utils.srgb_to_linear(c) for c in self._data(element, 'color')]
            blender_light.nwo.light_intensity = self._data(element, 'intensity')

            blender_light.shadow_soft_size = max((*self._data(element, 'near attenuation bounds'),)) * import_transform.scale_factor()
            nwo.light_far_attenuation_start, nwo.light_far_attenuation_end = [a * import_transform.scale_factor() for a in self._data(element, 'far attenuation bounds')]
            nwo.light_aspect = self._data(element, 'aspect')
            if self.required_field(element, 'flags').get_flag("invere squared falloff"):
                self.inverse_squared_lights.add(blender_light)

            definitions[element_index] = blender_light

        return definitions
