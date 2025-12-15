from math import radians
import bpy

from .. import utils

class NWO_LightPropertiesGroup(bpy.types.PropertyGroup):
    # LIGHTS #

    # light_game_type: bpy.props.EnumProperty(
    #     name="Light Game Type",
    #     options=set(),
    #     description="",
    #     default="_connected_geometry_bungie_light_type_default",
    #     items=[
    #         ("_connected_geometry_bungie_light_type_default", "Default", "Lightmap light. Requires lightmapping to complete for this light appear"),
    #         ("_connected_geometry_bungie_light_type_inlined", "Inlined", "For large lights"),
    #         ("_connected_geometry_bungie_light_type_rerender", "Rerender", "High quality shadowing light"),
    #         (
    #             "_connected_geometry_bungie_light_type_screen_space",
    #             "Screen Space",
    #             "Cheap low quality dynamic light",
    #         ),
    #         ("_connected_geometry_bungie_light_type_uber", "Uber", "High quality light"),
    #     ],
    # )

    light_shape: bpy.props.EnumProperty(
        name="Light Shape",
        options=set(),
        description="Whether the spot like should emit light in a circle or rectangle shape.",
        default="_connected_geometry_light_shape_circle",
        items=[
            ("_connected_geometry_light_shape_circle", "Circle", ""),
            ("_connected_geometry_light_shape_rectangle", "Rectangle", ""),
        ],
    )
    
    def update_light_far_attenuation_start(self, context):
        if not utils.get_scene_props().transforming:
            if self.light_far_attenuation_start > self.light_far_attenuation_end:
                self.light_far_attenuation_end = self.light_far_attenuation_start
            # elif self.light_far_attenuation_start < self.light_near_attenuation_end:
            #     self.light_near_attenuation_end = self.light_far_attenuation_start

    light_far_attenuation_start: bpy.props.FloatProperty(
        name="Light Falloff Start",
        options=set(),
        description="After this point, the light will begin to lose power. This value will be automatically calculated based on Blender light power in left at 0",
        default=0,
        min=0,
        subtype='DISTANCE',
        unit='LENGTH',
        update=update_light_far_attenuation_start,
    )
    
    def update_light_far_attenuation_end(self, context):
        if not utils.get_scene_props().transforming:
            if self.light_far_attenuation_end < self.light_far_attenuation_start:
                self.light_far_attenuation_start = self.light_far_attenuation_end

    light_far_attenuation_end: bpy.props.FloatProperty(
        name="Light Falloff End",
        options=set(),
        description="From the light falloff start, the light will gradually lose power until it reaches zero by the end point. This value will be automatically calculated based on Blender light power in left at 0",
        default=0,
        min=0,
        subtype='DISTANCE',
        unit='LENGTH',
        update=update_light_far_attenuation_end,
    )

    # light_volume_distance: bpy.props.FloatProperty(
    #     name="Light Volume Distance",
    #     options=set(),
    #     description="",
    # )

    # light_volume_intensity: bpy.props.FloatProperty(
    #     name="Light Volume Intensity",
    #     options=set(),
    #     description="",
    #     default=1.0,
    #     min=0.0,
    #     soft_max=10.0,
    #     subtype="FACTOR",
    # )

    # light_fade_start_distance: bpy.props.FloatProperty(
    #     name="Light Fade Out Start",
    #     options=set(),
    #     description="The light starts to fade out when the camera is x units away",
    #     default=utils.wu(100),
    #     subtype='DISTANCE',
    #     unit='LENGTH',
    # )

    # light_fade_end_distance: bpy.props.FloatProperty(
    #     name="Light Fade Out End",
    #     options=set(),
    #     description="The light completely fades out when the camera is x units away",
    #     default=utils.wu(150),
    #     subtype='DISTANCE',
    #     unit='LENGTH',
    # )
    
    def get_light_intensity(self):
        return utils.calc_light_intensity(self.id_data, utils.get_export_scale(bpy.context) ** 2)
    
    def set_light_intensity(self, value):
        self['light_intensity_value'] = value
        
    def update_light_intensity(self, context):
        if self.id_data.type != 'SUN':
            self.id_data.energy = utils.calc_light_energy(self.id_data, utils.get_export_scale(context) ** -2 * self.light_intensity_value)

    light_intensity: bpy.props.FloatProperty(
        name="Light Intensity",
        options=set(),
        description="The intensity of this light expressed in the units the game uses",
        get=get_light_intensity,
        set=set_light_intensity,
        update=update_light_intensity,
        min=0,
    )
    
    light_intensity_value: bpy.props.FloatProperty(options={'HIDDEN'})

    light_use_clipping: utils.bpy.props.BoolProperty(
        name="Light Uses Clipping",
        options=set(),
        description="",
        default=False,
    )

    light_clipping_size_x_pos: bpy.props.FloatProperty(
        name="Light Clipping Size X Forward",
        options=set(),
        description="",
        default=100,
    )

    light_clipping_size_y_pos: bpy.props.FloatProperty(
        name="Light Clipping Size Y Forward",
        options=set(),
        description="",
        default=100,
    )

    light_clipping_size_z_pos: bpy.props.FloatProperty(
        name="Light Clipping Size Z Forward",
        options=set(),
        description="",
        default=100,
    )

    light_clipping_size_x_neg: bpy.props.FloatProperty(
        name="Light Clipping Size X Backward",
        options=set(),
        description="",
        default=100,
    )

    light_clipping_size_y_neg: bpy.props.FloatProperty(
        name="Light Clipping Size Y Backward",
        options=set(),
        description="",
        default=100,
    )

    light_clipping_size_z_neg: bpy.props.FloatProperty(
        name="Light Clipping Size Z Backward",
        options=set(),
        description="",
        default=100,
    )

    light_falloff_shape: bpy.props.FloatProperty(
        name="Light Falloff Shape",
        options=set(),
        description="Describes how the intensity of light decays between the start and end of inner and outer radius of the spotlight beam",
        default=1,
        min=0.0,
    )

    light_aspect: bpy.props.FloatProperty(
        name="Light Aspect",
        options=set(),
        description="Aspect ratio of the rectangular spotlight",
        default=1,
        min=0.0,
    )

    # light_bounce_ratio: bpy.props.FloatProperty(
    #     name="Light Bounce Ratio",
    #     options=set(),
    #     description="",
    #     default=1,
    #     min=0.0,
    # )

    # light_screenspace_has_specular: bpy.props.BoolProperty(
    #     name="Screenspace Light Has Specular",
    #     options=set(),
    #     description="",
    #     default=False,
    # )

    # def light_tag_clean_tag_path(self, context):
    #     self["light_tag_override"] = utils.clean_tag_path(self["light_tag_override"]).strip(
    #         '"'
    #     )

    # light_tag_override: bpy.props.StringProperty(
    #     name="Light Tag Override",
    #     options=set(),
    #     description="",
    #     update=light_tag_clean_tag_path,
    # )

    # def light_shader_clean_tag_path(self, context):
    #     self["light_shader_reference"] = utils.clean_tag_path(
    #         self["light_shader_reference"]
    #     ).strip('"')

    # light_shader_reference: bpy.props.StringProperty(
    #     name="Light Shader Reference",
    #     options=set(),
    #     description="",
    #     update=light_shader_clean_tag_path,
    # )

    # def light_gel_clean_tag_path(self, context):
    #     self["light_gel_reference"] = utils.clean_tag_path(self["light_gel_reference"]).strip(
    #         '"'
    #     )

    # light_gel_reference: bpy.props.StringProperty(
    #     name="Light Gel Reference",
    #     options=set(),
    #     description="",
    #     update=light_gel_clean_tag_path,
    # )

    # def light_lens_flare_clean_tag_path(self, context):
    #     self["light_lens_flare_reference"] = utils.clean_tag_path(
    #         self["light_lens_flare_reference"]
    #     ).strip('"')

    # light_lens_flare_reference: bpy.props.StringProperty(
    #     name="Light Lens Flare Reference",
    #     options=set(),
    #     description="",
    #     update=light_lens_flare_clean_tag_path,
    # )

    # H4 LIGHT PROPERTIES
    
    light_physically_correct: bpy.props.BoolProperty(
        name="Light Physically Correct",
        description="Light uses power to determine light falloff and cutoff",
        options=set(),
    )
    
    light_dynamic_shadow_quality: bpy.props.EnumProperty(
        name="Shadow Quality",
        options=set(),
        description="",
        default="_connected_geometry_dynamic_shadow_quality_normal",
        items=[
            (
                "_connected_geometry_dynamic_shadow_quality_normal",
                "Normal",
                "",
            ),
            (
                "_connected_geometry_dynamic_shadow_quality_expensive",
                "Expensive",
                "",
            ),
        ],
    )

    light_specular_contribution: bpy.props.BoolProperty(
        name="Specular Contribution",
        options=set(),
        description="",
        default=True,
    )

    light_amplification_factor: bpy.props.FloatProperty(
        name="Indirect Amplification",
        options=set(),
        description="",
        default=0.5,
        subtype="FACTOR",
        min=0.0,
        soft_max=10.0,
    )

    light_attenuation_near_radius: bpy.props.FloatProperty(
        name="Near Attenuation Radius",
        options=set(),
        description="",
        default=0,
        min=0.0,
    )

    light_attenuation_far_radius: bpy.props.FloatProperty(
        name="Far Attenuation Radius",
        options=set(),
        description="",
        default=0,
        min=0.0,
    )

    light_attenuation_power: bpy.props.FloatProperty(
        name="Attenuation Power",
        options=set(),
        description="",
        default=0,
        min=0.0,
    )

    light_cinema_objects_only: bpy.props.BoolProperty(
        name="Only Light Cinematic Objects",
        options=set(),
        description="",
        default=False,
    )

    light_tag_name: bpy.props.StringProperty(
        name="Light Tag Name",
        options=set(),
        description="",
    )

    light_specular_power: bpy.props.FloatProperty(
        name="Specular Power",
        options=set(),
        description="",
        default=32,
        min=0.0,
    )

    light_specular_intensity: bpy.props.FloatProperty(
        name="Specular Intensity",
        options=set(),
        description="",
        default=0,
        min=0.0,
    )
    
    light_camera_fade_start: bpy.props.FloatProperty(
        name="Camera Fade Start",
        description="Distance at which this light begins to fade from the camera view",
        options=set(),
        default=0,
        min=0,
    )
    
    light_camera_fade_end: bpy.props.FloatProperty(
        name="Camera Fade End",
        description="Distance at which this light is completely invisible from the camera view",
        options=set(),
        default=0,
        min=0,
    )
    
    def get_light_strength(self):
        value = 1.0
        if not utils.is_corinth() or self.id_data.type == 'SUN':
            return 1.0
        
        if self.light_cinema_objects_only:
            return 0.0
        
        elif self.light_indirect_only:
            value = 0.01
        
        return min(value * self.light_amplification_factor, 0.001)
    
    light_strength: bpy.props.FloatProperty(
        get=get_light_strength,
    )

    light_cinema: bpy.props.EnumProperty(
        name="Cinematic Render",
        options=set(),
        description="Define whether this light should only render in cinematics, outside of cinematics, or always render",
        default="_connected_geometry_lighting_cinema_default",
        items=[
            ("_connected_geometry_lighting_cinema_default", "Always", ""),
            (
                "_connected_geometry_lighting_cinema_only",
                "Cinematics Only",
                "",
            ),
            ("_connected_geometry_lighting_cinema_exclude", "Exclude", ""),
        ],
    )

    light_cone_projection_shape: bpy.props.EnumProperty(
        name="Cone Projection Shape",
        options=set(),
        description="",
        default="_connected_geometry_cone_projection_shape_cone",
        items=[
            ("_connected_geometry_cone_projection_shape_cone", "Cone", ""),
            (
                "_connected_geometry_cone_projection_shape_frustum",
                "Frustum",
                "",
            ),
        ],
    )

    light_shadow_near_clipplane: bpy.props.FloatProperty(
        name="Shadow Near Clip Plane",
        options=set(),
        description="",
        default=0,
        min=0.0,
    )

    light_jitter_sphere_radius: bpy.props.FloatProperty(
        name="Light Jitter Sphere Radius",
        options=set(),
        description="",
        default=0,
        min=0.0,
    )

    light_shadow_far_clipplane: bpy.props.FloatProperty(
        name="Shadow Far Clip Plane",
        options=set(),
        description="",
        default=0,
        min=0.0,
    )

    light_shadow_bias_offset: bpy.props.FloatProperty(
        name="Shadow Bias Offset",
        options=set(),
        description="",
        default=0,
        min=0.0,
    )

    light_shadow_color: bpy.props.FloatVectorProperty(
        name="Shadow Color",
        options=set(),
        description="",
        default=(0.0, 0.0, 0.0),
        subtype="COLOR",
        min=0.0,
        max=1.0,
    )

    light_shadows: bpy.props.BoolProperty(
        name="Has Shadows",
        options=set(),
        description="",
        default=True,
    )

    light_sub_type: bpy.props.EnumProperty(
        name="Light Sub-Type",
        options=set(),
        description="",
        default="_connected_geometry_lighting_sub_type_default",
        items=[
            ("_connected_geometry_lighting_sub_type_default", "Default", ""),
            (
                "_connected_geometry_lighting_sub_type_screenspace",
                "Screenspace",
                "",
            ),
            ("_connected_geometry_lighting_sub_type_uber", "Uber", ""),
        ],
    )

    light_ignore_dynamic_objects: bpy.props.BoolProperty(
        name="Ignore Dynamic Objects",
        options=set(),
        description="",
        default=False,
    )

    light_diffuse_contribution: bpy.props.BoolProperty(
        name="Diffuse Contribution",
        options=set(),
        description="",
        default=True,
    )

    light_destroy_after: bpy.props.FloatProperty(
        name="Destroy After (seconds)",
        options=set(),
        description="Destroy the light after x seconds. 0 means the light is never destroyed",
        subtype="TIME",
        unit="TIME",
        step=100,
        default=0,
        min=0.0,
    )

    light_jitter_angle: bpy.props.FloatProperty(
        name="Light Jitter Angle",
        options=set(),
        description="",
        default=0,
        subtype='ANGLE'
    )

    light_jitter_quality: bpy.props.EnumProperty(
        name="Light Jitter Quality",
        options=set(),
        description="",
        default="_connected_geometry_light_jitter_quality_high",
        items=[
            ("_connected_geometry_light_jitter_quality_low", "Low", ""),
            ("_connected_geometry_light_jitter_quality_medium", "Medium", ""),
            ("_connected_geometry_light_jitter_quality_high", "High", ""),
        ],
    )

    light_indirect_only: bpy.props.BoolProperty(
        name="Indirect Only",
        options=set(),
        description="",
        default=False,
    )

    light_screenspace: bpy.props.BoolProperty(
        name="Screenspace Light",
        options=set(),
        description="",
        default=False,
    )

    light_static_analytic: bpy.props.BoolProperty(
        name="Static Analytic",
        options=set(),
        description="",
        default=False,
    )
    
    is_sun: bpy.props.BoolProperty(
        name="Is Sun",
        description="Specifies this light as a sun light",
        options=set(),
    )

    # light_mode: bpy.props.EnumProperty(
    #     name="Light Mode",
    #     options=set(),
    #     description="",
    #     default="_connected_geometry_light_mode_static",
    #     items=[
    #         (
    #             "_connected_geometry_light_mode_static",
    #             "Static",
    #             "Lights used in lightmapping",
    #         ),
    #         (
    #             "_connected_geometry_light_mode_dynamic",
    #             "Dynamic",
    #             "Lights that appear regardless of whether the map has been lightmapped",
    #         ),
    #         ("_connected_geometry_light_mode_analytic", "Analytic", "Similar to static lights but provides better results, however only one analytic light should ever light an object at a time"),
    #     ],
    # )
    
    # Emissive props
    
    light_quality: bpy.props.FloatProperty(
        name="Light Quality",
        options=set(),
        description="Controls the quality of the shadows cast by a complex occluder. For instance, a light casting shadows of tree branches on a wall would require a higher quality to get smooth shadows",
        default=1,
        min=0,
    )
    
    light_focus: bpy.props.FloatProperty(
        name="Light Focus",
        options=set(),
        description="Controls the spread of the light. 180 degrees will emit light in a hemisphere from each point, 0 degrees will emit light nearly perpendicular to the surface",
        min=0,
        default=radians(180), 
        max=radians(180),
        subtype="ANGLE",
    )
    
    light_use_shader_gel: bpy.props.BoolProperty(
        name="Use Shader Gel",
        options=set(),
        description="",
        default=False,
    )
    
    light_per_unit: bpy.props.BoolProperty(
        name="Light Per Unit",
        options=set(),
        description="When an light is scaled, determines if the amount of emitted light should be spread out across the surface or increased/decreased to keep a regular amount of light emission per unit area",
        default=False,
    )