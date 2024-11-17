import bpy

class NWO_OT_SkyGenerate(bpy.types.Operator):
    bl_idname = "nwo.sky_generate"
    bl_label = "Generate Sky"
    bl_description = "Generates a skydome and skylights ready for export to the game"
    bl_options = {'REGISTER', 'UNDO'}
    
    # Main params
    build_sky_from_map: bpy.props.BoolProperty()
    input_sky_map_name: bpy.props.StringProperty()
    generate_type: bpy.props.EnumProperty(
        name="Type",
        items=[
            ('BOTH', "Skylights & Skydome", ""),
            ('SKYLIGHT', "Skylights Only", ""),
            ('SKYDOME', "Skydome Only", ""),
        ]
    )
    
    lit_objects_by_sky: bpy.props.BoolProperty()
    generate_light_count: bpy.props.IntProperty(
        max=1024,
    )
    
    # Dome Params
    lattitude_slices: bpy.props.IntProperty(
        max=50,
    )
    longitude_slices: bpy.props.IntProperty(
        max=100,
    )
    horizontal_fov: bpy.props.FloatProperty()
    vertical_fov: bpy.props.FloatProperty()
    
    # Light params
    sun_theta: bpy.props.FloatProperty()
    sun_phi: bpy.props.FloatProperty()
    turpidity: bpy.props.FloatProperty()
    sky_type: bpy.props.EnumProperty()
    cie_sky_number: bpy.props.IntProperty()
    sky_intensity: bpy.props.FloatProperty()
    sun_intensity: bpy.props.FloatProperty()
    luminance_only: bpy.props.IntProperty()
    exposure: bpy.props.FloatProperty()
    sun_cone_angle: bpy.props.FloatProperty()
    custom_sun_color_override: bpy.props.BoolProperty()
    sun_color: bpy.props.FloatVectorProperty()
    sky_dome_radius: bpy.props.FloatProperty()
    zenith_color: bpy.props.FloatVectorProperty()
    haze_color: bpy.props.FloatVectorProperty()
    override_zenith_color: bpy.props.BoolProperty()
    override_horizon_color: bpy.props.BoolProperty()
    horizon_haze_height: bpy.props.FloatProperty()
    sun_blur: bpy.props.FloatProperty()
    
    

    def execute(self, context):
        self.build_dome()
        return {"FINISHED"}
    
    def build_dome(self):
        result = False
        mesh = None
        
        
    def build_sky_dome_mesh(self) -> bool:
        if not self.input_sky_map_name:
            return False
        
        sky_image = self.load_image(self.input_sky_map_name)
        if not sky_image:
            return False
        
        num_of_verts = self.lattitude_slices * self.longitude_slices
        num_of_faces = (self.lattitude_slices - 1) * (self.longitude_slices - 1) * 2

    def load_image(self):
        pass
    
    def generate_lights(self): ...
    
    def lit_object(self): ...
    
#=============================================================================
# sky constants taken from Preetham's analytical sky model
#=============================================================================

# Distribution coefficients for the luminance(Y) distribution function
YDC = (
    (0.1787, -1.4630),
    (-0.3554, 0.4275),
    (-0.0227, 5.3251),
    (0.1206, -2.5771),
    (-0.0670, 0.3703),
)

# Distribution coefficients for the x distribution function
xDC = (
    (-0.0193, -0.2592),
    (-0.0665, 0.0008),
    (-0.0004, 0.2125),
    (-0.0641, -0.8989),
    (-0.0033, 0.0452),
)

# Distribution coefficients for the y distribution function
yDC = (
    (-0.0167, -0.2608),
    (-0.0950, 0.0092),
    (-0.0079, 0.2102),
    (-0.0441, -1.6537),
    (-0.0109, 0.0529),
)

# Zenith x value
xZC = (
    (0.00166, -0.00375, 0.00209, 0.0),
    (-0.02903, 0.06377, -0.03203, 0.00394),
    (0.11693, -0.21196, 0.06052, 0.25886),
)

# Zenith y value
yZC = (
    (0.00275, -0.00610, 0.00317, 0.0),
    (-0.04214, 0.08970, -0.04153, 0.00516),
    (0.15346, -0.26756, 0.06670, 0.26688),
)

# Perez parameter ranges
perez_parameter_ranges = (
    (-1.6, 0.8),
    (-2.0, 0.0),
    (0.0, 25.0),
    (-6.0, -2.0),
    (0.0, 1.4),
)



class SkyGen:
    def build_dome_to_file(sky_image_name: str, error_message)