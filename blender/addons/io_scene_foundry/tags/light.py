


from math import radians, isfinite, pi

from .bitmap import bitmap_to_image
from .. import utils
from .blender import BlenderTag
from .backend import TagDocument
from .metadata import enum_index, rgba
from .light_functions import light_functions, constant_light_value
from .. import import_transform
import bpy


def h3_falloff(maximum_distance: float, distance_diffusion: float,
               angular_smoothness: float) -> tuple[float, float, float]:
    """Approximate H3's diffusion curve with Foundry's linear fade interval.

    H3 stores a hard maximum and a diffusion control rather than Reach's start
    and end distances. More diffusion keeps the light visible farther out.
    """
    maximum_distance = max(0.0, maximum_distance) if isfinite(maximum_distance) else 0.0
    distance_diffusion = max(0.0, distance_diffusion) if isfinite(distance_diffusion) else 0.0
    angular_smoothness = max(0.0, angular_smoothness) if isfinite(angular_smoothness) else 0.0
    start = maximum_distance * distance_diffusion / (1.0 + distance_diffusion)
    spot_blend = angular_smoothness / (1.0 + angular_smoothness)
    return start, maximum_distance, spot_blend


class LightTag(BlenderTag, TagDocument):
    tag_ext = 'light'
        
    def __init__(self, path='', **kwargs):
        kwargs.setdefault('tag_must_exist', False)
        super().__init__(path, **kwargs)
        
    def _to_blender_reach(self, primary_scale, secondary_scale, attachment):
        with light_functions(self, ('color', 'intensity')) as functions:
            return self._convert(primary_scale, secondary_scale, attachment, *functions)

    def _to_blender_halo1(self, primary_scale, secondary_scale, attachment):
        """Import an H1 light without interpreting its colors as Reach mappings.

        H1's radiosity intensity/color are lightmap settings, not the dynamic
        light's power. ARGB bounds supply the dynamic color and brightness.
        Radius modulation and cube-map gels need a dedicated H1 light shader;
        retain the radius settings and use the maximum radius for the preview.
        """
        root = self.tag.root()
        shape = self.required_field(root, 'shape').as_struct()
        color = self.required_field(root, 'color').as_struct()
        radius = max(0.0, self.value(shape, 'radius'))
        cutoff = self.value(shape, 'cutoff angle')
        falloff = self.value(shape, 'falloff angle')
        lower = rgba(self.value(color, 'color lower bound'))
        upper = rgba(self.value(color, 'color upper bound'))
        # The native H1 schema retains Guerilla's misspelling.
        modifiers = self.value(shape, 'radius modifer')
        # Zero bounds are commonly authored (including the hunter fuelrod
        # flare); H1 treats these as the default multiplier of one.
        radius_bounds = tuple(v if v else 1.0 for v in (modifiers.lower, modifiers.upper))
        flags = self.required_field(color, 'interpolation flags')
        hsv = flags.get_flag('blend in hsv')
        # Native H1 angles are radians (unlike the later light layouts).
        is_spot = 0.0 < cutoff < pi
        data = bpy.data.lights.new(self.tag_path.ShortName, type='SPOT' if is_spot else 'POINT')
        data.color = [utils.srgb_to_linear(c) for c in upper[:3]]
        data.nwo.light_intensity = max(0.0, upper[3])
        data.nwo.light_far_attenuation_start = 0.0
        data.nwo.light_far_attenuation_end = import_transform.distance(radius * max(radius_bounds))
        data.shadow_soft_size = 0.0
        if is_spot:
            # H1 stores the angle from the axis; Blender stores the full cone.
            data.spot_size = min(2.0 * cutoff, pi)
            data.spot_blend = max(0.0, min(1.0, 1.0 - falloff / cutoff))
        light_node = utils.make_halo_light(data)
        tree = data.node_tree
        if primary_scale:
            attribute = tree.nodes.new('ShaderNodeAttribute')
            attribute.attribute_type = 'INSTANCER'
            attribute.attribute_name = primary_scale
            ramp = tree.nodes.new('ShaderNodeValToRGB')
            ramp.label = 'H1 color and brightness bounds'
            ramp.color_ramp.color_mode = 'HSV' if hsv else 'RGB'
            ramp.color_ramp.elements[0].color = (*[utils.srgb_to_linear(c) for c in lower[:3]], lower[3])
            ramp.color_ramp.elements[1].color = (*data.color, upper[3])
            tree.links.new(attribute.outputs['Fac'], ramp.inputs['Fac'])
            tree.links.new(ramp.outputs['Color'], light_node.inputs[0])
            tree.links.new(ramp.outputs['Alpha'], light_node.inputs[1])
        else:
            light_node.inputs[0].default_value = (*data.color, 1.0)
            light_node.inputs[1].default_value = max(0.0, upper[3])
        data['halo1_radius'] = radius
        data['halo1_radius_modifier'] = radius_bounds
        data['halo1_color_lower_bound'] = lower
        data['halo1_color_upper_bound'] = upper
        data['halo1_secondary_scale'] = secondary_scale
        data.nwo.light_specular_contribution = not self.required_field(root, 'flags').get_flag('no specular')
        if attachment is not None:
            attachment.function_names.update(name for name in (primary_scale, secondary_scale) if name)
        utils.arrange(tree)
        return data

    def _convert(self, primary_scale, secondary_scale, attachment, color_function, intensity_function):
        root = self.tag.root()
        is_spot_light = enum_index(self.value(root, 'type'), ('sphere', 'frustum')) == 1
        h3_falloff_values = None
        if self.game in {'halo3', 'halo3odst'}:
            h3_falloff_values = h3_falloff(
                self.value(root, 'maximum distance'),
                self.value(root, 'distance diffusion'),
                self.value(root, 'angular smoothness'))
        data = bpy.data.lights.new(self.tag_path.ShortName, type='SPOT' if is_spot_light else 'POINT')
        # intensity_scale = 1
        if is_spot_light:
            # intensity_scale = 100
            hotspot_cutoff_size = self.value(root, 'frustum field of view')
            data.spot_size = radians(hotspot_cutoff_size)
            if h3_falloff_values is not None:
                data.spot_blend = h3_falloff_values[2]
            elif hotspot_cutoff_size > 0.0:
                data.spot_blend = 1 - self.value(root, 'angular hotspot') / hotspot_cutoff_size
                
        data.shadow_soft_size = 0.5 * (1 / 0.03048) * import_transform.scale_factor()
        
        
        color_node = None
        color_function_name = f"{self.tag_path.ShortName}_color"
        if color_function.is_basic_function:
            data.color = [utils.srgb_to_linear(c) for c in color_function.colors[0][:3]]
        else:
            color_node = color_function.to_blend_nodes(name=color_function_name)
        
        
        strength_node = None
        intensity_function_name = f"{self.tag_path.ShortName}_strength"
        
        if h3_falloff_values is not None:
            atten_falloff, atten_cutoff, _ = h3_falloff_values
        else:
            atten_falloff = self.value(root, 'attenuation start distance')
            atten_cutoff = self.value(root, 'attenuation end distance')
        data.nwo.light_far_attenuation_start = import_transform.distance(atten_falloff)
        data.nwo.light_far_attenuation_end = import_transform.distance(atten_cutoff)
        
        if intensity_function.is_basic_function:
            data.nwo.light_intensity = intensity_function.clamp_min
        else:
            data.nwo.light_intensity = intensity_function.clamp_max
            strength_node = intensity_function.to_blend_nodes(name=intensity_function_name, normalize=True)
        
        if attachment is not None:
            if intensity_function.input:
                attachment.function_names.add(intensity_function.input)
            if intensity_function.range and intensity_function.is_ranged:
                attachment.function_names.add(intensity_function.range)
            if intensity_function.output_modifier and intensity_function.output_modifier_type.value > 0:
                attachment.function_names.add(intensity_function.output_modifier)
                
        gobo_tag_path = self.reference(root, 'gel bitmap')
        gobo_image = None
        if self.path_exists(gobo_tag_path):
            gobo_info = bitmap_to_image(gobo_tag_path.Filename)
            if gobo_info.image:
                gobo_image = gobo_info.image

        utils.make_halo_light(data, primary_scale, secondary_scale, color_node, strength_node, gobo_image)
        
        return data
    
    def _to_blender_corinth(self, primary_scale, secondary_scale, attachment):
        from .connected_material import Function
        parameters = self.required_field(self.tag.root(), 'Midnight_Light_Parameters').as_struct()
        value = lambda name: self.value(parameters, name)
        light_type = enum_index(value('Light Type'), ('Point', 'Spot', 'Directional', 'Area', 'Sun'))
        if light_type == 3:
            raise NotImplementedError('Area light-tag conversion is not implemented')
        names = ['Intensity', 'Distance Attenuation End']
        if light_type == 1:
            names.append('Outer Cone End')
        functions = {}
        for name in names:
            function = Function()
            function.from_native_light(self, self.required_field(parameters, name).as_struct())
            functions[name] = function

        # Resolve all required metadata before allocating a Blender light.
        physically_correct = enum_index(value('Lighting Mode'), ('Physically Correct', 'Artistic')) == 0
        static_values = {name: constant_light_value(function) for name, function in functions.items()}
        for name in names[1:]:
            if static_values[name] is None:
                raise NotImplementedError(f'Animated {name} in H4/H2AMP light tags is not implemented')
        intensity = functions['Intensity']
        animated_intensity = static_values['Intensity'] is None
        if animated_intensity and (physically_correct or light_type in {2, 4}):
            raise NotImplementedError('Animated physical/directional H4/H2AMP light intensity is not implemented')
        if intensity.is_color:
            raise ValueError('Light intensity must be a scalar function')
        if animated_intensity and not (isfinite(max(intensity.clamp_min, intensity.clamp_max))
                                       and max(intensity.clamp_min, intensity.clamp_max) > 0):
            raise NotImplementedError('Animated light intensity requires a finite positive normalization scale')
        projection = enum_index(value('Cone Projection Shape'), ('Cone', 'Frustum'))
        # Older Midnight layouts predate these settings. Leave Blender's defaults
        # for absent properties; do not reinterpret the legacy Shadow Edge Filter.
        quality = (enum_index(value('Dynamic Shadow Quality'), ('Normal', 'Expensive (cinematics only)'))
                   if parameters.field('Dynamic Shadow Quality') is not None else None)
        for name in ('Barn Door Left', 'Barn Door Right', 'Barn Door Top', 'Barn Door Bottom'):
            if parameters.field(name) is not None and value(name) != 0:
                raise NotImplementedError('Legacy light barn-door clipping is not implemented')
        if parameters.field('Clip Volume Shape') is not None and value('Clip Volume Shape') not in ('None', 0):
            raise NotImplementedError('Legacy light clip volumes are not implemented')
        booleans = {name: enum_index(value(name), ('Off', 'On')) == 1 for name in (
            'Shadows', 'Screenspace Light', 'Ignore Dynamic Objects', 'Cinema Objects Only',
            'Cinema Only', 'Cinema Exclude', 'Specular Contribution', 'Diffuse Contribution')
            if name != 'Cinema Objects Only' or parameters.field(name) is not None}
        color = value('Light Color')
        rgb = (color.red, color.green, color.blue)
        attenuation_start = import_transform.distance(value('Distance Attenuation Start'))
        attenuation_end = import_transform.distance(static_values['Distance Attenuation End'])
        inner_cone = value('Inner Cone Angle')
        shadow_near, shadow_far, shadow_bias = (value(name) if parameters.field(name) is not None else None for name in (
            'Shadow Near Clip Plane', 'Shadow Far Clip Plane', 'Shadow Bias Offset'))
        gobo_path = self.reference(parameters, 'Gobo Tag Path')
        if (physically_correct or light_type in {2, 4}) and (primary_scale or secondary_scale or self.path_exists(gobo_path)):
            raise NotImplementedError('Linked or projected physical/directional H4/H2AMP lights are not implemented')
        gobo_image = None
        if self.path_exists(gobo_path):
            gobo_image = bitmap_to_image(gobo_path.Filename).image

        kind = ('POINT', 'SPOT', 'SUN', 'AREA', 'SUN')[light_type]
        data = bpy.data.lights.new(self.tag_path.ShortName, type=kind)
        data.color = [utils.srgb_to_linear(c) for c in rgb]
        nwo = data.nwo
        nwo.light_intensity = max(intensity.clamp_min, intensity.clamp_max) if animated_intensity else static_values['Intensity']
        nwo.light_physically_correct = physically_correct
        nwo.light_far_attenuation_start = attenuation_start
        nwo.light_far_attenuation_end = attenuation_end
        if kind == 'SPOT':
            outer_cone = static_values['Outer Cone End']
            data.spot_size = radians(outer_cone)
            if outer_cone > 0:
                data.spot_blend = max(0., min(1., 1 - inner_cone / outer_cone))
        nwo.light_cone_projection_shape = '_connected_geometry_cone_projection_shape_' + ('cone', 'frustum')[projection]
        if shadow_near is not None:
            nwo.light_shadow_near_clipplane = shadow_near
        if shadow_far is not None:
            nwo.light_shadow_far_clipplane = shadow_far
        if shadow_bias is not None:
            nwo.light_shadow_bias_offset = shadow_bias
        if quality is not None:
            nwo.light_dynamic_shadow_quality = '_connected_geometry_dynamic_shadow_quality_' + ('normal', 'expensive')[quality]
        for prop, name in (
            ('light_shadows', 'Shadows'), ('light_screenspace', 'Screenspace Light'),
            ('light_ignore_dynamic_objects', 'Ignore Dynamic Objects'),
            ('light_cinema_objects_only', 'Cinema Objects Only'),
            ('light_specular_contribution', 'Specular Contribution'),
            ('light_diffuse_contribution', 'Diffuse Contribution')):
            if name in booleans:
                setattr(nwo, prop, booleans[name])
        if booleans['Cinema Only']:
            nwo.light_cinema = '_connected_geometry_lighting_cinema_only'
        if booleans['Cinema Exclude']:
            nwo.light_cinema = '_connected_geometry_lighting_cinema_exclude'
        if kind == 'SUN':
            data.energy = nwo.light_intensity
        elif physically_correct:
            data.energy = nwo.light_intensity * utils.get_import_scale(bpy.context) ** 2
        else:
            strength = intensity.to_blend_nodes(name=f'{self.tag_path.ShortName}_strength', normalize=True) if animated_intensity else None
            utils.make_halo_light(data, primary_scale, secondary_scale, strength_node_tree=strength, gobo_image=gobo_image)
        if attachment is not None and animated_intensity:
            if intensity.uses_input:
                attachment.function_names.add(intensity.input)
            if intensity.is_ranged and intensity.range:
                attachment.function_names.add(intensity.range)
            if intensity.output_modifier_type.value and intensity.output_modifier:
                attachment.function_names.add(intensity.output_modifier)
        return data
        
    def to_blender(self, primary_scale="", secondary_scale="", attachment=None):
        if self.game == 'halo1':
            return self._to_blender_halo1(primary_scale, secondary_scale, attachment)
        elif self.corinth:
            return self._to_blender_corinth(primary_scale, secondary_scale, attachment)
        else:
            return self._to_blender_reach(primary_scale, secondary_scale, attachment)
