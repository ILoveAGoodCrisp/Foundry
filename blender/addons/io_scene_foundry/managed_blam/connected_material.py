

from enum import Enum, auto

# OPTIONS

class AlbedoOption(Enum):
    default = 0
    detail_blend = 1
    constant_color = 2
    two_change_color = 3
    four_change_color = 4
    three_detail_blend = 5
    two_detail_overlay = 6
    two_detail = 7
    color_mask = 8
    two_detail_black_point = 9
    four_change_color_applying_to_specular = 10
    simple = 11
    
class BumpMappingOption(Enum):
    off = 0
    standard = 1
    detail = 2
    detail_blend = 3
    three_detail_blend = 4
    standard_wrinkle = 5
    detail_wrinkle = 6

class AlphaTestOption(Enum):
    none = 0
    simple = 1
    
class SpecularMaskOption(Enum):
    no_specular_mask = 0
    specular_mask_from_diffuse = 1
    specular_mask_mult_diffuse = 2
    specular_mask_from_texture = 3
    
class MaterialModelOption(Enum):
    diffuse_only = 0
    cook_torrance = 1
    two_lobe_phong = 2
    foliage = 3
    none = 4
    organism = 5
    hair = 6
    
class EnvironmentMappingOption(Enum):
    none = 0
    per_pixel = 1
    dynamic = 2
    from_flat_texture = 3
    
class SelfIlluminationOption(Enum):
    off = 0
    simple = 1
    _3_channel_self_illum = 2
    plasma = 3
    from_diffuse = 4
    illum_detail = 5
    meter = 6
    self_illum_times_diffuse = 7
    simple_with_alpha_mask = 8
    multiply_additive = 9
    palettized_plasma = 10
    change_color = 11
    change_color_detail = 12
    
class BlendModeOption(Enum):
    opaque = 0
    additive = 1
    multiply = 2
    alpha_blend = 3
    double_multiple = 4
    pre_multiplied_alpha = 5
    
class ParallaxOption(Enum):
    off = 0
    simple = 1
    interpolated = 2
    simple_detail = 3
    
class MiscOption(Enum):
    default = 0
    rotating_bitmaps_super_slow = 1
    
class WetnessOption(Enum):
    default = 0
    flood = 1
    proof = 2
    simple = 3
    ripples = 4
    
class AlphaBlendSourceOption(Enum):
    from_albedo_without_fresnel = 0
    from_albedo_alpha = 1
    from_opacity_map_alpha = 2
    from_opacity_map_rgb = 3
    from_opacity_map_alpha_and_albedo_alpha = 4
    
# Parameters

class ParameterType(Enum):
    bitmap = 0
    color = 1
    real = 2
    _int = 3
    _bool = 4
    arg_color = 5
    
class FilterMode(Enum):
    pass
    
class Parameter:
    name: str
    type: ParameterType
    bitmap: str
    real: int
    int_bool: int
    flags: int
    filter_mode: FilterMode
    address_mode: int
    address_mode_x: int
    address_mode_y: int
    anisotropy_amount: int
    extern_rtt_mode: int
    sharpen_mode: int

class AnimatedParameter:
    pass

