

from enum import Enum

from .. import utils
from .Tags import TagFieldBlockElement
import bpy

ammo_names = "primary_ammunition_ones", "primary_ammunition_tens", "primary_ammunition_hundreds"

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
    
    
class FunctionEditorColorGraphType(Enum):
    Scalar = 0
    OneColor = 1
    TwoColor = 2
    ThreeColor = 3
    FourColor = 4
    
class FunctionEditorMasterType(Enum):
    Basic = 0
    Curve = 1
    Periodic = 2
    Exponent = 3
    Transition = 4
    
class FunctionEditorSegmentCornerType(Enum):
    NotApplicable = 0
    Corner = 1
    Smooth = 2
    
class FunctionEditorSegmentType(Enum):
    Linear = 0
    Spline = 1
    Spline2 = 2
    
# class FunctionEditorPeriodicType(Enum):
#     One = 0
#     Zero = 1
#     Cosine = 2
#     CosineVariable = 3
#     DiagonalWave = 4
#     DiagonalWaveVariable = 5
#     Slide = 6
#     SlideVariable = 7
#     Noise = 8
#     Jitter = 9
#     Wander = 10
#     Spark = 11
    
# class FunctionEditorTransitionType(Enum):
#     Linear = 0
#     Early = 1
#     VeryEarly = 2
#     Late = 3
#     VeryLate = 4
#     Cosine = 5
#     One = 6
#     Zero = 7
    
class AnimatedParameterType(Enum):
    VALUE = 0
    COLOR = 1
    SCALE_UNIFORM = 2
    SCALE_X = 3
    SCALE_Y = 4
    TRANSLATION_X = 5
    TRANSLATION_Y = 6
    FRAME_INDEX = 7
    ALPHA = 8
    
class TilingNodeInputs(Enum):
    TRANSLATION_X = 0
    TRANSLATION_Y = 1
    SCALE_UNIFORM = 2
    SCALE_X = 3
    SCALE_Y = 4
    
class GameFunctionType(Enum):
    OBJECT = 0
    WORLD = 1
    CONSTANT = 2
    
class GameFunction:
    def __init__(self, name: str, default_value: float, function_type: GameFunctionType, nwo_prop_name=""):
        self.name = name
        self.default_value = default_value
        self.function_type = function_type
        self.attribute_type = 'VIEW_LAYER' if function_type == GameFunctionType.WORLD else 'INSTANCER'
        self.nwo_prop_name = nwo_prop_name
    
# GAME FUNCTION DEFAULTS
functions_list = [
    # OBJECT
    GameFunction("active_shield_vitality", 1, GameFunctionType.OBJECT),
    GameFunction("alive", True, GameFunctionType.OBJECT),
    GameFunction("all_quiet", True, GameFunctionType.OBJECT),
    GameFunction("animation_event_function_a", 0, GameFunctionType.OBJECT),
    GameFunction("animation_event_function_b", 0, GameFunctionType.OBJECT),
    GameFunction("animation_event_function_c", 0, GameFunctionType.OBJECT),
    GameFunction("animation_event_function_d", 0, GameFunctionType.OBJECT),
    GameFunction("animation_event_function_e", 0, GameFunctionType.OBJECT),
    GameFunction("animation_event_function_f", 0, GameFunctionType.OBJECT),
    GameFunction("animation_event_function_g", 0, GameFunctionType.OBJECT),
    GameFunction("animation_event_function_h", 0, GameFunctionType.OBJECT),
    GameFunction("animation_event_function_i", 0, GameFunctionType.OBJECT),
    GameFunction("animation_event_function_j", 0, GameFunctionType.OBJECT),
    GameFunction("animation_event_function_k", 0, GameFunctionType.OBJECT),
    GameFunction("animation_event_function_l", 0, GameFunctionType.OBJECT),
    GameFunction("animation_event_function_left_grip", 0, GameFunctionType.OBJECT),
    GameFunction("animation_event_function_m", 0, GameFunctionType.OBJECT),
    GameFunction("animation_event_function_n", 0, GameFunctionType.OBJECT),
    GameFunction("animation_event_function_o", 0, GameFunctionType.OBJECT),
    GameFunction("animation_event_function_p", 0, GameFunctionType.OBJECT),
    GameFunction("animation_event_function_q", 0, GameFunctionType.OBJECT),
    GameFunction("animation_event_function_r", 0, GameFunctionType.OBJECT),
    GameFunction("animation_event_function_right_grip", 0, GameFunctionType.OBJECT),
    GameFunction("animation_event_function_s", 0, GameFunctionType.OBJECT),
    GameFunction("animation_event_function_t", 0, GameFunctionType.OBJECT),
    GameFunction("animation_event_function_u", 0, GameFunctionType.OBJECT),
    GameFunction("animation_event_function_v", 0, GameFunctionType.OBJECT),
    GameFunction("animation_event_function_w", 0, GameFunctionType.OBJECT),
    GameFunction("animation_event_function_x", 0, GameFunctionType.OBJECT),
    GameFunction("animation_event_function_y", 0, GameFunctionType.OBJECT),
    GameFunction("animation_event_function_z", 0, GameFunctionType.OBJECT),
    GameFunction("animation_object_function_a", 0, GameFunctionType.OBJECT),
    GameFunction("animation_object_function_b", 0, GameFunctionType.OBJECT),
    GameFunction("animation_object_function_c", 0, GameFunctionType.OBJECT),
    GameFunction("animation_object_function_d", 0, GameFunctionType.OBJECT),
    GameFunction("balling", False, GameFunctionType.OBJECT),
    GameFunction("balling_beserk", False, GameFunctionType.OBJECT),
    GameFunction("body_vitality", 1, GameFunctionType.OBJECT),
    GameFunction("cinematic_in_progress", False, GameFunctionType.WORLD, "cinematic_in_progress"), # bpy.context.scene.nwo.asset_type == "cinematic"
    GameFunction("compass", 0, GameFunctionType.OBJECT, "compass"), # GET BY DIRECTION
    GameFunction("cortana_rampancy", 0, GameFunctionType.OBJECT),
    GameFunction("current_body_damage", 0, GameFunctionType.OBJECT),
    GameFunction("current_shield_damage", 0, GameFunctionType.OBJECT),
    GameFunction("dismembered_arm_left", False, GameFunctionType.OBJECT),
    GameFunction("dismembered_arm_right", False, GameFunctionType.OBJECT),
    GameFunction("dismembered_head", False, GameFunctionType.OBJECT),
    GameFunction("dismembered_leg_left", False, GameFunctionType.OBJECT),
    GameFunction("dismembered_leg_right", False, GameFunctionType.OBJECT),
    GameFunction("dissolving_amount", 0, GameFunctionType.OBJECT),
    GameFunction("dissolving_or_camo", False, GameFunctionType.OBJECT),
    GameFunction("electrical_power", 1, GameFunctionType.OBJECT),
    GameFunction("emerging", False, GameFunctionType.OBJECT),
    GameFunction("engine_value_a", 0, GameFunctionType.OBJECT),
    GameFunction("engine_value_b", 0, GameFunctionType.OBJECT),
    GameFunction("engine_value_c", 0, GameFunctionType.OBJECT),
    GameFunction("engine_value_d", 0, GameFunctionType.OBJECT),
    GameFunction("flashlights_allowed", True, GameFunctionType.WORLD),
    GameFunction("forerunner_eye_glow", 1, GameFunctionType.OBJECT),
    GameFunction("holiday", False, GameFunctionType.WORLD, "holiday"), # 1 if its a holiday, else 0. Needs an NWO prop
    GameFunction("impending_reinforcement", 0, GameFunctionType.OBJECT),
    GameFunction("in_phantom", 0, GameFunctionType.OBJECT),
    GameFunction("megalo_object_function_1", 0, GameFunctionType.OBJECT),
    GameFunction("megalo_object_function_2", 0, GameFunctionType.OBJECT),
    GameFunction("megalo_object_function_3", 0, GameFunctionType.OBJECT),
    GameFunction("megalo_object_function_4", 0, GameFunctionType.OBJECT),
    GameFunction("megalo_object_function_5", 0, GameFunctionType.OBJECT),
    GameFunction("megalo_object_function_6", 0, GameFunctionType.OBJECT),
    GameFunction("megalo_object_function_7", 0, GameFunctionType.OBJECT),
    GameFunction("megalo_object_timer_function", 0, GameFunctionType.OBJECT),
    GameFunction("megalo_object_timer_function_hundreds", 0, GameFunctionType.OBJECT),
    GameFunction("megalo_object_timer_function_ones", 0, GameFunctionType.OBJECT),
    GameFunction("megalo_object_timer_function_present", 0, GameFunctionType.OBJECT),
    GameFunction("megalo_object_timer_function_tens", 0, GameFunctionType.OBJECT),
    GameFunction("morse_code", 0, GameFunctionType.OBJECT),
    GameFunction("object_overshield_amount", 0, GameFunctionType.OBJECT),
    GameFunction("oddball_effect", 0, GameFunctionType.OBJECT),
    GameFunction("one", 1, GameFunctionType.CONSTANT),
    GameFunction("phantom_on", False, GameFunctionType.OBJECT),
    GameFunction("phantom_power", 0, GameFunctionType.OBJECT),
    GameFunction("phantom_speed", 0, GameFunctionType.OBJECT),
    GameFunction("rain_intensity", 0, GameFunctionType.WORLD),
    GameFunction("random_constant", 0, GameFunctionType.WORLD), # foundry will select a random float on blender load
    GameFunction("render_time", 0, GameFunctionType.OBJECT),
    GameFunction("scripted_object_function_a", 0, GameFunctionType.OBJECT),
    GameFunction("scripted_object_function_b", 0, GameFunctionType.OBJECT),
    GameFunction("scripted_object_function_c", 0, GameFunctionType.OBJECT),
    GameFunction("scripted_object_function_d", 0, GameFunctionType.OBJECT),
    GameFunction("self_illum_color", 0, GameFunctionType.OBJECT),
    GameFunction("self_illum_intensity", 0, GameFunctionType.OBJECT),
    GameFunction("self_illum_on", False, GameFunctionType.OBJECT),
    GameFunction("shield_depleted", False, GameFunctionType.OBJECT),
    GameFunction("shield_vitality", 1, GameFunctionType.OBJECT),
    GameFunction("teleporter_active", True, GameFunctionType.OBJECT),
    GameFunction("time", 0, GameFunctionType.WORLD, "time"),
    GameFunction("time_hours", 0, GameFunctionType.WORLD, "time_hours"),
    GameFunction("time_minutes", 0, GameFunctionType.WORLD, "time_minutes"),
    GameFunction("time_seconds", 0, GameFunctionType.WORLD, "time_seconds"),
    GameFunction("var_obj_local_a", 0, GameFunctionType.OBJECT),
    GameFunction("var_obj_local_b", 0, GameFunctionType.OBJECT),
    GameFunction("var_obj_local_c", 0, GameFunctionType.OBJECT),
    GameFunction("variant", 0, GameFunctionType.OBJECT), # set based on (variant_count - 1) / variant_index 
    GameFunction("zero", 0, GameFunctionType.CONSTANT),
    # UNIT
    GameFunction("acceleration_forward", 0, GameFunctionType.OBJECT),
    GameFunction("acceleration_lateral", 0, GameFunctionType.OBJECT),
    GameFunction("acceleration_magnitude", 0, GameFunctionType.OBJECT),
    GameFunction("acceleration_magnitude2d", 0, GameFunctionType.OBJECT),
    GameFunction("acceleration_pitch", 0, GameFunctionType.OBJECT),
    GameFunction("acceleration_vertical", 0, GameFunctionType.OBJECT),
    GameFunction("acceleration_yaw", 0, GameFunctionType.OBJECT),
    GameFunction("active_camouflage", 0, GameFunctionType.OBJECT),
    GameFunction("aim_pitch", 0, GameFunctionType.OBJECT),
    GameFunction("aim_yaw", 0, GameFunctionType.OBJECT),
    GameFunction("aiming_change", 0, GameFunctionType.OBJECT),
    GameFunction("animation_throttle_forward", 0, GameFunctionType.OBJECT),
    GameFunction("animation_throttle_lateral", 0, GameFunctionType.OBJECT),
    GameFunction("animation_throttle_magnitude", 0, GameFunctionType.OBJECT),
    GameFunction("animation_throttle_magnitude2d", 0, GameFunctionType.OBJECT),
    GameFunction("animation_throttle_pitch", 0, GameFunctionType.OBJECT),
    GameFunction("animation_throttle_vertical", 0, GameFunctionType.OBJECT),
    GameFunction("animation_throttle_yaw", 0, GameFunctionType.OBJECT),
    GameFunction("armory_open", False, GameFunctionType.OBJECT),
    GameFunction("audio_movement_angle", 0, GameFunctionType.OBJECT),
    GameFunction("audio_movement_speed", 0, GameFunctionType.OBJECT),
    GameFunction("barrel_spin", 0, GameFunctionType.OBJECT),
    GameFunction("birth_progress", 0, GameFunctionType.OBJECT),
    GameFunction("boost", 0, GameFunctionType.OBJECT),
    GameFunction("boost_power_meter", 0, GameFunctionType.OBJECT),
    GameFunction("boost_recharge", 0, GameFunctionType.OBJECT),
    GameFunction("can_blink", True, GameFunctionType.OBJECT),
    GameFunction("crouch", False, GameFunctionType.OBJECT),
    GameFunction("driver_seat_occupied", False, GameFunctionType.OBJECT),
    GameFunction("driver_seat_power", 0, GameFunctionType.OBJECT),
    GameFunction("emp_disabled", False, GameFunctionType.OBJECT),
    GameFunction("emp_fraction", 0, GameFunctionType.OBJECT),
    GameFunction("enter_progress", 0, GameFunctionType.OBJECT),
    GameFunction("exit_progress", 0, GameFunctionType.OBJECT),
    GameFunction("gear_position", 0, GameFunctionType.OBJECT),
    GameFunction("gunner_seat_occupied", False, GameFunctionType.OBJECT),
    GameFunction("gunner_seat_power", 0, GameFunctionType.OBJECT),
    GameFunction("horizontal_aiming_change", 0, GameFunctionType.OBJECT),
    GameFunction("impulse_channel_valid", True, GameFunctionType.OBJECT),
    GameFunction("integrated_light_power", 0, GameFunctionType.OBJECT),
    GameFunction("jump_offset_forward", 0, GameFunctionType.OBJECT),
    GameFunction("jump_offset_lateral", 0, GameFunctionType.OBJECT),
    GameFunction("jump_offset_pitch", 0, GameFunctionType.OBJECT),
    GameFunction("jump_offset_vertical", 0, GameFunctionType.OBJECT),
    GameFunction("jump_offset_yaw", 0, GameFunctionType.OBJECT),
    GameFunction("left_grip", 0, GameFunctionType.OBJECT),
    GameFunction("mouth_aperture", 0, GameFunctionType.OBJECT),
    GameFunction("move_offset_forward", 0, GameFunctionType.OBJECT),
    GameFunction("move_offset_lateral", 0, GameFunctionType.OBJECT),
    GameFunction("move_offset_pitch", 0, GameFunctionType.OBJECT),
    GameFunction("move_offset_vertical", 0, GameFunctionType.OBJECT),
    GameFunction("move_offset_yaw", 0, GameFunctionType.OBJECT),
    GameFunction("night_vision", 0, GameFunctionType.OBJECT),
    GameFunction("object_pitch", 0, GameFunctionType.OBJECT),
    GameFunction("object_yaw", 0, GameFunctionType.OBJECT),
    GameFunction("out_of_bounds", False, GameFunctionType.OBJECT),
    GameFunction("phase_progress", 0, GameFunctionType.OBJECT),
    GameFunction("resurrect_progress", 0, GameFunctionType.OBJECT),
    GameFunction("right_grip", 0, GameFunctionType.OBJECT),
    GameFunction("state_channel_playback_ratio", 0, GameFunctionType.OBJECT),
    GameFunction("terminal_velocity_fall_weight", 0, GameFunctionType.OBJECT),
    GameFunction("throttle_forward", 0, GameFunctionType.OBJECT),
    GameFunction("throttle_side", 0, GameFunctionType.OBJECT),
    GameFunction("throttle_vertical", 0, GameFunctionType.OBJECT),
    GameFunction("transition_channel_playback_ratio", 0, GameFunctionType.OBJECT),
    GameFunction("transition_channel_valid", True, GameFunctionType.OBJECT),
    GameFunction("turning_desired_pitch", 0, GameFunctionType.OBJECT),
    GameFunction("turning_desired_yaw", 0, GameFunctionType.OBJECT),
    GameFunction("turning_velocity_pitch", 0, GameFunctionType.OBJECT),
    GameFunction("turning_velocity_yaw", 0, GameFunctionType.OBJECT),
    GameFunction("unit_closed", True, GameFunctionType.OBJECT),
    GameFunction("unit_closing", False, GameFunctionType.OBJECT),
    GameFunction("unit_open", False, GameFunctionType.OBJECT),
    GameFunction("unit_opening", False, GameFunctionType.OBJECT),
    GameFunction("velocity_forward", 0, GameFunctionType.OBJECT),
    GameFunction("velocity_lateral", 0, GameFunctionType.OBJECT),
    GameFunction("velocity_magnitude", 0, GameFunctionType.OBJECT),
    GameFunction("velocity_mangitude2d", 0, GameFunctionType.OBJECT),
    GameFunction("velocity_pitch", 0, GameFunctionType.OBJECT),
    GameFunction("velocity_yaw", 0, GameFunctionType.OBJECT),
    GameFunction("velocity_thrust", 0, GameFunctionType.OBJECT),
    GameFunction("weapon_illumination", 0, GameFunctionType.OBJECT),
    GameFunction("zoom_level", 0, GameFunctionType.OBJECT),
    # Scenario Interpolator
    GameFunction("scenario_interpolator1", 0, GameFunctionType.WORLD),
    GameFunction("scenario_interpolator2", 0, GameFunctionType.WORLD),
    GameFunction("scenario_interpolator3", 0, GameFunctionType.WORLD),
    GameFunction("scenario_interpolator4", 0, GameFunctionType.WORLD),
    GameFunction("scenario_interpolator5", 0, GameFunctionType.WORLD),
    GameFunction("scenario_interpolator6", 0, GameFunctionType.WORLD),
    GameFunction("scenario_interpolator7", 0, GameFunctionType.WORLD),
    GameFunction("scenario_interpolator8", 0, GameFunctionType.WORLD),
    GameFunction("scenario_interpolator9", 0, GameFunctionType.WORLD),
    GameFunction("scenario_interpolator10", 0, GameFunctionType.WORLD),
    GameFunction("scenario_interpolator11", 0, GameFunctionType.WORLD),
    GameFunction("scenario_interpolator12", 0, GameFunctionType.WORLD),
    GameFunction("scenario_interpolator13", 0, GameFunctionType.WORLD),
    GameFunction("scenario_interpolator14", 0, GameFunctionType.WORLD),
    GameFunction("scenario_interpolator15", 0, GameFunctionType.WORLD),
    GameFunction("scenario_interpolator16", 0, GameFunctionType.WORLD),
    GameFunction("scenario_interpolator17", 0, GameFunctionType.WORLD),
    GameFunction("scenario_interpolator18", 0, GameFunctionType.WORLD),
    GameFunction("scenario_interpolator19", 0, GameFunctionType.WORLD),
    GameFunction("scenario_interpolator20", 0, GameFunctionType.WORLD),
    GameFunction("scenario_interpolator21", 0, GameFunctionType.WORLD),
    GameFunction("scenario_interpolator22", 0, GameFunctionType.WORLD),
    GameFunction("scenario_interpolator23", 0, GameFunctionType.WORLD),
    GameFunction("scenario_interpolator24", 0, GameFunctionType.WORLD),
    GameFunction("scenario_interpolator25", 0, GameFunctionType.WORLD),
    GameFunction("scenario_interpolator26", 0, GameFunctionType.WORLD),
    GameFunction("scenario_interpolator27", 0, GameFunctionType.WORLD),
    GameFunction("scenario_interpolator28", 0, GameFunctionType.WORLD),
    GameFunction("scenario_interpolator29", 0, GameFunctionType.WORLD),
    GameFunction("scenario_interpolator30", 0, GameFunctionType.WORLD),
    GameFunction("scenario_interpolator31", 0, GameFunctionType.WORLD),
    GameFunction("scenario_interpolator32", 0, GameFunctionType.WORLD),
    # Biped
    GameFunction("combat_status", 0, GameFunctionType.OBJECT),
    GameFunction("cortana_hud_rampancy", 0, GameFunctionType.OBJECT),
    GameFunction("flight", False, GameFunctionType.OBJECT),
    GameFunction("flight_animation_mode", 0, GameFunctionType.OBJECT),
    GameFunction("flying_speed", 0, GameFunctionType.OBJECT),
    GameFunction("grenade_collected", False, GameFunctionType.OBJECT),
    GameFunction("jetpack_exhaust", 0, GameFunctionType.OBJECT),
    GameFunction("mandibles", 0, GameFunctionType.OBJECT),
    GameFunction("player_is_female", False, GameFunctionType.OBJECT),
    GameFunction("player_is_sprinting", False, GameFunctionType.OBJECT),
    GameFunction("player_is_sprinting_local", False, GameFunctionType.OBJECT),
    GameFunction("player_spint_charge", 0, GameFunctionType.OBJECT),
    GameFunction("shield_projected", False, GameFunctionType.OBJECT),
    GameFunction("stunned", False, GameFunctionType.OBJECT),
    # Creature
    GameFunction("shooting", False, GameFunctionType.OBJECT),
    # Device
    GameFunction("change_in_power", 0, GameFunctionType.OBJECT),
    GameFunction("change_in_position", 0, GameFunctionType.OBJECT),
    GameFunction("cooldown", 0, GameFunctionType.OBJECT),
    GameFunction("delay", 0, GameFunctionType.OBJECT),
    GameFunction("locked", False, GameFunctionType.OBJECT),
    GameFunction("position", 0, GameFunctionType.OBJECT),
    GameFunction("power", 1, GameFunctionType.OBJECT),
    GameFunction("ready", True, GameFunctionType.OBJECT),
    # Equipment
    GameFunction("age", 0, GameFunctionType.OBJECT),
    GameFunction("death", False, GameFunctionType.OBJECT),
    GameFunction("energy", 1, GameFunctionType.OBJECT),
    GameFunction("energy_burned", 0, GameFunctionType.OBJECT),
    GameFunction("evade_back", False, GameFunctionType.OBJECT),
    GameFunction("evade_front", False, GameFunctionType.OBJECT),
    GameFunction("evade_left", False, GameFunctionType.OBJECT),
    GameFunction("evade_right", False, GameFunctionType.OBJECT),
    GameFunction("jetpack_height", 0, GameFunctionType.OBJECT),
    GameFunction("on", False, GameFunctionType.OBJECT),
    # Vehicle
    GameFunction("abs_throttle", 0, GameFunctionType.OBJECT),
    GameFunction("anti_gravity_engine_position", 0, GameFunctionType.OBJECT),
    GameFunction("anti_gravity_strength", 0, GameFunctionType.OBJECT),
    GameFunction("auto_trigger_primary_fire", 0, GameFunctionType.OBJECT),
    GameFunction("auto_trigger_secondary_fire", 0, GameFunctionType.OBJECT),
    GameFunction("back_left_tire_position", 0, GameFunctionType.OBJECT),
    GameFunction("back_left_tire_velocity", 0, GameFunctionType.OBJECT),
    GameFunction("back_right_tire_position", 0, GameFunctionType.OBJECT),
    GameFunction("back_right_tire_velocity", 0, GameFunctionType.OBJECT),
    GameFunction("boost", 0, GameFunctionType.OBJECT),
    GameFunction("emitting", False, GameFunctionType.OBJECT),
    GameFunction("engine_cruising", 0, GameFunctionType.OBJECT),
    GameFunction("engine_power", 0, GameFunctionType.OBJECT),
    GameFunction("engine_power_left", 0, GameFunctionType.OBJECT),
    GameFunction("engine_power_right", 0, GameFunctionType.OBJECT),
    GameFunction("engine_rpm", 0, GameFunctionType.OBJECT),
    GameFunction("engine_turbo", 0, GameFunctionType.OBJECT),
    GameFunction("fake_audio_speed", 0, GameFunctionType.OBJECT),
    GameFunction("flying", False, GameFunctionType.OBJECT),
    GameFunction("front_left_tire_position", 0, GameFunctionType.OBJECT),
    GameFunction("front_left_tire_velocity", 0, GameFunctionType.OBJECT),
    GameFunction("front_right_tire_position", 0, GameFunctionType.OBJECT),
    GameFunction("front_right_tire_velocity", 0, GameFunctionType.OBJECT),
    GameFunction("front_wheels_ground_speed_fraction", 0, GameFunctionType.OBJECT),
    GameFunction("hover", 0, GameFunctionType.OBJECT),
    GameFunction("in_reverse", False, GameFunctionType.OBJECT),
    GameFunction("jump", False, GameFunctionType.OBJECT),
    GameFunction("landing", False, GameFunctionType.OBJECT),
    GameFunction("left_tread_position", 0, GameFunctionType.OBJECT),
    GameFunction("left_tread_velocity", 0, GameFunctionType.OBJECT),
    GameFunction("mean_anitgrav", 0, GameFunctionType.OBJECT),
    GameFunction("move_timer", 0, GameFunctionType.OBJECT),
    GameFunction("phase", 0, GameFunctionType.OBJECT),
    GameFunction("rear_wheels_ground_speed_fraction", 0, GameFunctionType.OBJECT),
    GameFunction("right_tread_position", 0, GameFunctionType.OBJECT),
    GameFunction("right_tread_velocity", 0, GameFunctionType.OBJECT),
    GameFunction("sentry_alert", False, GameFunctionType.OBJECT),
    GameFunction("sentry_attack", False, GameFunctionType.OBJECT),
    GameFunction("sentry_idle", False, GameFunctionType.OBJECT),
    GameFunction("sentry_secondary_gun", False, GameFunctionType.OBJECT),
    GameFunction("sentry_tracking_target", False, GameFunctionType.OBJECT),
    GameFunction("slide_absolute", 0, GameFunctionType.OBJECT),
    GameFunction("slide_left", 0, GameFunctionType.OBJECT),
    GameFunction("slide_right", 0, GameFunctionType.OBJECT),
    GameFunction("speed_absolute", 0, GameFunctionType.OBJECT),
    GameFunction("speed_backward", 0, GameFunctionType.OBJECT),
    GameFunction("speed_forward", 0, GameFunctionType.OBJECT),
    GameFunction("speed_slide_maximum", 0, GameFunctionType.OBJECT),
    GameFunction("surge", 0, GameFunctionType.OBJECT),
    GameFunction("taking_off", False, GameFunctionType.OBJECT),
    GameFunction("thrust", 0, GameFunctionType.OBJECT),
    GameFunction("tread_grind", 0, GameFunctionType.OBJECT),
    GameFunction("turn_absolute", 0, GameFunctionType.OBJECT),
    GameFunction("turn_left", 0, GameFunctionType.OBJECT),
    GameFunction("turn_right", 0, GameFunctionType.OBJECT),
    GameFunction("vehicle_occupied", False, GameFunctionType.OBJECT),
    GameFunction("vehicle_roll", 0, GameFunctionType.OBJECT),
    GameFunction("velocity_air", 0, GameFunctionType.OBJECT),
    GameFunction("velocity_forward", 0, GameFunctionType.OBJECT),
    GameFunction("velocity_ground", 0, GameFunctionType.OBJECT),
    GameFunction("velocity_left", 0, GameFunctionType.OBJECT),
    GameFunction("velocity_up", 0, GameFunctionType.OBJECT),
    GameFunction("velocity_water", 0, GameFunctionType.OBJECT),
    GameFunction("wingtip_contrail", 0, GameFunctionType.OBJECT),
    GameFunction("wingtip_contrail_new", 0, GameFunctionType.OBJECT),
    # Projectile
    GameFunction("acceleration_range", 0, GameFunctionType.OBJECT),
    GameFunction("bounce", 0, GameFunctionType.OBJECT),
    GameFunction("damage_scale", 0, GameFunctionType.OBJECT),
    GameFunction("projectile_attach", 0, GameFunctionType.OBJECT),
    GameFunction("range_remaining", 0, GameFunctionType.OBJECT),
    GameFunction("speed_absolute", 0, GameFunctionType.OBJECT),
    GameFunction("tethered_detonation_time", 0, GameFunctionType.OBJECT),
    GameFunction("tethered_to_local_player", 0, GameFunctionType.OBJECT),
    GameFunction("tethered_to_local_player", 0, GameFunctionType.OBJECT),
    GameFunction("time_remaining", 0, GameFunctionType.OBJECT),
    GameFunction("tracer", 0, GameFunctionType.OBJECT),
    # Item
    GameFunction("in_inventory", False, GameFunctionType.OBJECT),
    # Weapon
    GameFunction("airstrike_fire_percentage", 0, GameFunctionType.OBJECT),
    GameFunction("airstrike_launch_count_ones", 0, GameFunctionType.OBJECT),
    GameFunction("airstrike_state", 0, GameFunctionType.OBJECT),
    GameFunction("airstrike_warmup", 0, GameFunctionType.OBJECT),
    GameFunction("flashlight_intensity", 0, GameFunctionType.OBJECT),
    GameFunction("heat", 0, GameFunctionType.OBJECT),
    GameFunction("illumination", 0, GameFunctionType.OBJECT),
    GameFunction("iron_sights", False, GameFunctionType.OBJECT),
    GameFunction("is_reloading", False, GameFunctionType.OBJECT),
    GameFunction("is_venting", False, GameFunctionType.OBJECT),
    GameFunction("overheated", False, GameFunctionType.OBJECT),
    GameFunction("post_reload_timeout", 0, GameFunctionType.OBJECT),
    GameFunction("power", 1, GameFunctionType.OBJECT),
    GameFunction("primary_ammunition", 0, GameFunctionType.OBJECT),
    GameFunction("primary_ammunition_ones", 0, GameFunctionType.OBJECT),
    GameFunction("primary_ammunition_tens", 0, GameFunctionType.OBJECT),
    GameFunction("primary_barrel_firing", False, GameFunctionType.OBJECT),
    GameFunction("primary_barrel_dual_left", False, GameFunctionType.OBJECT),
    GameFunction("primary_barrel_dual_right", False, GameFunctionType.OBJECT),
    GameFunction("primary_barrel_firing_single", False, GameFunctionType.OBJECT),
    GameFunction("primary_charged", False, GameFunctionType.OBJECT),
    GameFunction("primary_charged_with_cooldown", False, GameFunctionType.OBJECT),
    GameFunction("primary_ejection_port", 0, GameFunctionType.OBJECT),
    GameFunction("primary_firing", False, GameFunctionType.OBJECT),
    GameFunction("primary_firing_ticks", 0, GameFunctionType.OBJECT),
    GameFunction("primary_is_spewing", False, GameFunctionType.OBJECT),
    GameFunction("primary_total_ammuniation", 0, GameFunctionType.OBJECT),
    GameFunction("primary_trigger_down", False, GameFunctionType.OBJECT),
    GameFunction("scaleshot_power", 0, GameFunctionType.OBJECT),
    GameFunction("secondary_ammunition", 0, GameFunctionType.OBJECT),
    GameFunction("secondary_barrel_firing", False, GameFunctionType.OBJECT),
    GameFunction("secondary_charged", False, GameFunctionType.OBJECT),
    GameFunction("secondary_charged_with_cooldown", False, GameFunctionType.OBJECT),
    GameFunction("secondary_ejection_port", 0, GameFunctionType.OBJECT),
    GameFunction("secondary_firing", False, GameFunctionType.OBJECT),
    GameFunction("secondary_rate_of_fire", 0, GameFunctionType.OBJECT),
    GameFunction("primary_spew", 0, GameFunctionType.OBJECT),
    GameFunction("secondary_total_ammuniation", 0, GameFunctionType.OBJECT),
    GameFunction("secondary_trigger_down", False, GameFunctionType.OBJECT),
    GameFunction("stowed", False, GameFunctionType.OBJECT),
    GameFunction("tether_distance", 0, GameFunctionType.OBJECT),
    GameFunction("tether_exploded", False, GameFunctionType.OBJECT),
    GameFunction("tether_linked_transition", 0, GameFunctionType.OBJECT),
    GameFunction("tether_projectile", 0, GameFunctionType.OBJECT),
    GameFunction("tether_state", 0, GameFunctionType.OBJECT),
    GameFunction("tether_trigger", 0, GameFunctionType.OBJECT),
    GameFunction("turned_on", True, GameFunctionType.OBJECT),
    GameFunction("turning_on", False, GameFunctionType.OBJECT),
    GameFunction("venting_time", 0, GameFunctionType.OBJECT),
    GameFunction("warthog_chaingun_illumination", 0, GameFunctionType.OBJECT),
]

game_functions = {func.name: func for func in functions_list}
    
def add_attribute_node(tree: bpy.types.NodeTree, function_name: str):
    group = bpy.data.node_groups.get(function_name)
    if group is None:
        func = game_functions.get(function_name)
        if func is None:
            attr_node = tree.nodes.new('ShaderNodeAttribute')
            attr_node.attribute_name = function_name
            utils.print_warning(f"Failed to find game function: {function_name}")
            attr_node.attribute_type = 'INSTANCER'
        elif func.function_type == GameFunctionType.CONSTANT:
            attr_node = tree.nodes.new('ShaderNodeValue')
            attr_node.outputs[0].default_value = func.default_value
        else:
            attr_node = tree.nodes.new('ShaderNodeAttribute')
            attr_node.attribute_name = function_name
            attr_node.attribute_type = func.attribute_type

        return attr_node
    else:
        group_node = tree.nodes.new('ShaderNodeGroup')
        group_node.node_tree = group
        return group_node
    
class ControlPoint:
    def __init__(self, graph_index, point_index):
        self.graph_index = graph_index
        self.point_index = point_index
        self.x = 0
        self.y = 0
        self.corner_type = FunctionEditorSegmentCornerType.NotApplicable
        self.segment = None
        
    def from_editor(self, editor, last_point_index):
        game_point_2d = editor.GetControlPoint(self.graph_index, self.point_index)
        self.x = game_point_2d.X
        self.y = game_point_2d.Y
        if self.point_index > 0 and self.point_index < last_point_index:
            self.corner_type = FunctionEditorSegmentCornerType[editor.GetControlPointCornerType(self.graph_index, self.point_index).ToString()]
        
class Segment:
    def __init__(self, graph_index, segment_index):
        self.graph_index = graph_index
        self.segment_index = segment_index
        self.type = FunctionEditorSegmentType.Linear
        
    def from_editor(self, editor):
        self.type = FunctionEditorSegmentType[editor.GetSegmentType(self.graph_index, self.segment_index).ToString()]
        
class Interpolation:
    def __init__(self):
        self.interpolation_mode = None
        self.linear_travel_time = 0
        self.acceleration = 0
        self.spring_k = 0
        self.spring_c = 0
        self.fraction = 0
    
class Function:
    def __init__(self):
        self.time_period = 0.0
        self.input = ""
        self.range = ""
        self.input_uses_group_node = False
        self.range_uses_group_node = False
        self.is_ranged = False
        self.master_type = FunctionEditorMasterType.Basic
        self.is_color = False
        self.color_type = FunctionEditorColorGraphType.Scalar
        self.color_count = 1
        self.input_periodic_function = "one"
        self.range_periodic_function = "one"
        self.input_transition_function = "linear"
        self.range_transition_function = "linear"
        self.input_frequency = 0
        self.range_frequency = 0
        self.input_phase = 0
        self.range_phase = 0
        self.input_exponent = 5
        self.range_exponent = 5
        self.input_min = 0
        self.input_max = 1
        self.range_min = 0
        self.range_max = 1
        self.clamp_min = 0
        self.clamp_max = 1
        self.is_exclusion = False
        self.exclusion_min = 0
        self.exclusion_max = 0
        self.colors = [tuple((1, 1, 1)), tuple((1, 1, 1)), tuple((1, 1, 1)), tuple((1, 1, 1))]
        self.control_points = []
        
        self.time_period = 0
        self.input = ""
        self.range = ""
        self.ranged_interpolation_name = ""
        self.min_value = ""
        self.turn_off_with = ""
        
        self.invert = False
        self.mapping_does_not_controls_active = False
        self.always_active = False
        self.random_time_offset = False
        self.always_exports_value = False
        self.turn_off_with_uses_magnitude = False
        
        self.scale_by = ""
        self.interpolation_symmetric = None
        self.interpolation_increasing = None
        self.interpolation_decreasing = None
    
    def from_element(self, element: TagFieldBlockElement, block_name: str):
        editor = element.SelectField(block_name).Value
        self.is_ranged = editor.IsRanged
        self.master_type = FunctionEditorMasterType(editor.MasterType.value__)
        self.color_type = FunctionEditorColorGraphType(editor.ColorGraphType.value__)
        self.is_color = self.color_type != FunctionEditorColorGraphType.Scalar
        self.color_count = editor.ColorCount
        
        self.is_exclusion = editor.IsExclusion
        self.exclusion_min = editor.ExclusionMin
        self.exclusion_max = editor.ExclusionMax
        
        if block_name == "default function": # indicates that function comes from an object tag
            self.input = element.SelectField("import name").GetStringData()
            self.range = self.input
            self.turn_off_with = element.SelectField("turn off with").GetStringData()
            self.ranged_interpolation_name = element.SelectField("ranged interpolation name").GetStringData()
            self.min_value = element.SelectField("min value").Data
            self.scale_by = element.SelectField("scale by").GetStringData()
            flags = element.SelectField("flags")
            self.invert = flags.TestBit("invert")
            self.mapping_does_not_controls_active = flags.TestBit("mapping does not controls active")
            self.always_active = flags.TestBit("always active")
            self.random_time_offset = flags.TestBit("random time offset")
            self.always_exports_value = flags.TestBit("always exports value")
            self.turn_off_with_uses_magnitude = flags.TestBit("turn off with uses magnitude")
        else: # function comes from shader
            self.time_period = element.SelectField("time period").Data
            self.input = element.SelectField("input name").GetStringData()
            self.range = element.SelectField("range name").GetStringData()
        
        match self.master_type:
            case FunctionEditorMasterType.Periodic:
                self.input_periodic_function = editor.GetPeriodicFunctionText(editor.GetFunctionIndex(0))
                self.input_frequency = editor.GetFrequency(0)
                self.input_phase = editor.GetPhase(0)
                self.input_min = editor.GetAmplitudeMin(0)
                self.input_max = editor.GetAmplitudeMax(0)
                if self.is_ranged:
                    self.range_periodic_function = editor.GetPeriodicFunctionText(editor.GetFunctionIndex(1))
                    self.range_frequency = editor.GetFrequency(1)
                    self.range_phase = editor.GetPhase(1)
                    self.range_min = editor.GetAmplitudeMin(1)
                    self.range_max = editor.GetAmplitudeMax(1)
            case FunctionEditorMasterType.Exponent:
                self.input_exponent = editor.GetExponent(0)
                self.input_min = editor.GetAmplitudeMin(0)
                self.input_max = editor.GetAmplitudeMax(0)
                if self.is_ranged:
                    self.range_exponent = editor.GetExponent(1)
                    self.range_min = editor.GetAmplitudeMin(1)
                    self.range_max = editor.GetAmplitudeMax(1)
            case FunctionEditorMasterType.Transition:
                self.input_transition_function = editor.GetTransitionFunctionText(editor.GetFunctionIndex(0))
                self.input_min = editor.GetAmplitudeMin(0)
                self.input_max = editor.GetAmplitudeMax(0)
                if self.is_ranged:
                    self.range_transition_function = editor.GetTransitionFunctionText(editor.GetFunctionIndex(1))
                    self.range_min = editor.GetAmplitudeMin(1)
                    self.range_max = editor.GetAmplitudeMax(1)
            case FunctionEditorMasterType.Curve:
                pass
                # Loop segments
                # Get segment type, if spline then each CP on segment has a handle (another CP)
                
                
                # input_control_count = editor.GetControlPointCount(0)
                # segment_count = editor.GetSegmentCount(0)
                # last_control_index = input_control_count - 1
                # for i in range(input_control_count):
                #     control_point = ControlPoint(0, i)
                #     control_point.from_editor(editor, segment_count)
                #     if i < segment_count:
                #         segment = Segment(0, i)
                #         segment.from_editor(editor)
                #         control_point.segment = segment
                #     self.control_points.append(control_point)
                    
        if self.is_color:
            for i in range(self.color_count):
                game_color = editor.GetColor(i)
                if game_color.ColorMode == 1:
                    game_color = game_color.ToRgb()
                
                self.colors[i] = game_color.Red, game_color.Green, game_color.Blue, game_color.Alpha
        else:
            self.clamp_min = editor.ClampRangeMin
            self.clamp_max = editor.ClampRangeMax
            
    
    def to_element(self, element: TagFieldBlockElement, animated_function):
        element.SelectField("time period").Data = self.time_period
        editor = element.SelectField(animated_function).Value
        editor.BeginUpdate()
        # Do stuff
        editor.EndUpdate()
        
    def to_blend_nodes(self, tree: bpy.types.NodeTree=None, name="") -> list[bpy.types.Nodes]:
        '''Creates blender nodes for a game function, returns the output'''
        return_node_group = False
        if tree is None:
            return_node_group = True
            tree = bpy.data.node_groups.get(name)
            if tree is not None:
                return tree
            tree = bpy.data.node_groups.new(name, 'ShaderNodeTree')
            group_output = tree.nodes.new('NodeGroupOutput')
            if self.color_type == FunctionEditorColorGraphType.Scalar:
                tree.interface.new_socket("Value", in_out='OUTPUT', socket_type='NodeSocketFloat').default_value = 0.0
            else:
                tree.interface.new_socket("Color", in_out='OUTPUT', socket_type='NodeSocketColor').default_value = (1.0, 1.0, 1.0, 1.0)
        
        if self.master_type == FunctionEditorMasterType.Basic:
            if self.color_type == FunctionEditorColorGraphType.Scalar:
                node = tree.nodes.new('ShaderNodeValue')
                node.outputs[0].default_value = self.clamp_min
                if self.is_ranged:
                    node_range = tree.nodes.new('ShaderNodeValue')
                    node_range.outputs[0].default_value = self.clamp_max
                    node_mix = tree.nodes.new('ShaderNodeMix')
                    node_attribute = add_attribute_node(tree, self.ranged_interpolation_name)
                    tree.links.new(input=node_mix.inputs["A"], output=node.outputs[0])
                    tree.links.new(input=node_mix.inputs["B"], output=node_range.outputs[0])
                    tree.links.new(input=node_mix.inputs["Factor"], output=node_attribute.outputs[2] if node_attribute.bl_idname == 'ShaderNodeAttribute' else node_attribute.outputs[0])
            else:
                node = tree.nodes.new('ShaderNodeRGB')
                node.outputs[0].default_value = self.colors[0]
                if self.is_ranged:
                    node_range = tree.nodes.new('ShaderNodeRGB')
                    node_range.outputs[0].default_value = self.colors[1]
                    node_mix = tree.nodes.new('ShaderNodeMix')
                    node_mix.data_type = 'RGBA'
                    node_attribute = add_attribute_node(tree, self.ranged_interpolation_name)
                    tree.links.new(input=node_mix.inputs["A"], output=node.outputs[0])
                    tree.links.new(input=node_mix.inputs["B"], output=node_range.outputs[0])
                    tree.links.new(input=node_mix.inputs["Factor"], output=node_attribute.outputs[0])
            
            if return_node_group:
                tree.links.new(input=group_output.inputs[0], output=node_mix.outputs[0])
                return tree
            else:
                return node_mix.outputs[0]
        
        function_node = tree.nodes.new('ShaderNodeGroup')
        first_node_input = function_node
        first_node_range = function_node
        
        # print(self.tag_path.ShortName, data.color_type.name, data.master_type.name)
        
        match self.color_type:
            case FunctionEditorColorGraphType.Scalar:
                function_node.node_tree = utils.add_node_from_resources("reach_nodes", "Function - 2-float")
                function_node.inputs[1].default_value = self.clamp_min
                function_node.inputs[2].default_value = self.clamp_max
            case FunctionEditorColorGraphType.TwoColor:
                function_node.node_tree = utils.add_node_from_resources("reach_nodes", "Function - 2-color")
                function_node.inputs[1].default_value = self.colors[0]
                function_node.inputs[2].default_value = self.colors[1]
            case FunctionEditorColorGraphType.ThreeColor:
                function_node.node_tree = utils.add_node_from_resources("reach_nodes", "Function - 3-color")
                function_node.inputs[1].default_value = self.colors[0]
                function_node.inputs[2].default_value = self.colors[1]
                function_node.inputs[3].default_value = self.colors[2]
            case FunctionEditorColorGraphType.FourColor:
                function_node.node_tree = utils.add_node_from_resources("reach_nodes", "Function - 4-color")
                function_node.inputs[1].default_value = self.colors[0]
                function_node.inputs[2].default_value = self.colors[1]
                function_node.inputs[3].default_value = self.colors[2]
                function_node.inputs[4].default_value = self.colors[3]
        
        if self.master_type not in {FunctionEditorMasterType.Basic, FunctionEditorMasterType.Curve}:
            clamp_node = tree.nodes.new('ShaderNodeClamp')
            clamp_node.inputs["Max"].default_value = self.input_max
            clamp_node.inputs["Min"].default_value = self.input_min
            if self.is_ranged:
                clamp_node_ranged = tree.nodes.new('ShaderNodeClamp')
                clamp_node_ranged.inputs["Max"].default_value = self.range_max
                clamp_node_ranged.inputs["Min"].default_value = self.range_min
                mix_clamp_node = tree.nodes.new('ShaderNodeMix')
                mix_clamp_node.clamp_factor = True
                mix_clamp_node.inputs[0].default_value = 0.5
                tree.links.new(input=mix_clamp_node.inputs["A"], output=clamp_node.outputs[0])
                tree.links.new(input=mix_clamp_node.inputs["B"], output=clamp_node_ranged.outputs[0])
                tree.links.new(input=function_node.inputs[0], output=mix_clamp_node.outputs[0])
                first_node_input = clamp_node
                first_node_range = clamp_node_ranged
            else:
                tree.links.new(input=function_node.inputs[0], output=clamp_node.outputs[0])
                first_node_input = clamp_node
                
        if self.master_type != FunctionEditorMasterType.Basic and self.is_exclusion:
            exclusion_node = tree.nodes.new('ShaderNodeGroup')
            periodic_node.node_tree = utils.add_node_from_resources("shared_nodes", "Exclusion")
        
        match self.master_type:
            case FunctionEditorMasterType.Curve:
                curve_node = tree.nodes.new('ShaderNodeFloatCurve')
                tree.links.new(input=first_node_input.inputs[0], output=curve_node.outputs[0])
                first_node_input = curve_node
                if self.is_ranged:
                    curve_node_range = tree.nodes.new('ShaderNodeFloatCurve')
                    tree.links.new(input=first_node_range.inputs[0], output=curve_node_range.outputs[0])
                    first_node_range = curve_node_range
            case FunctionEditorMasterType.Periodic:
                periodic_node = tree.nodes.new('ShaderNodeGroup')
                periodic_node.node_tree = utils.add_node_from_resources("reach_nodes", f"periodic function type - {self.input_periodic_function}")
                if self.input_periodic_function not in {"one", "zero"}:
                    periodic_node.inputs[1].default_value = self.input_frequency
                    periodic_node.inputs[2].default_value = self.input_phase
                tree.links.new(input=first_node_input.inputs[0], output=periodic_node.outputs[0])
                first_node_input = periodic_node
                if self.is_ranged:
                    periodic_node_range = tree.nodes.new('ShaderNodeGroup')
                    periodic_node_range.node_tree = utils.add_node_from_resources("reach_nodes", f"periodic function type - {self.range_periodic_function}")
                    if self.range_periodic_function not in {"one", "zero"}:
                        periodic_node_range.inputs[1].default_value = self.range_frequency
                        periodic_node_range.inputs[2].default_value = self.range_phase
                    tree.links.new(input=first_node_range.inputs[0], output=periodic_node_range.outputs[0])
                    first_node_range = periodic_node_range
            case FunctionEditorMasterType.Exponent:
                math_node = tree.nodes.new('ShaderNodeMath')
                math_node.operation = 'POWER'
                math_node.inputs[1].default_value = self.input_exponent
                tree.links.new(input=first_node_input.inputs[0], output=math_node.outputs[0])
                first_node_input = math_node
                if self.is_ranged:
                    math_node_range = tree.nodes.new('ShaderNodeMath')
                    math_node_range.operation = 'POWER'
                    math_node_range.inputs[1].default_value = self.range_exponent
                    tree.links.new(input=first_node_range.inputs[0], output=math_node_range.outputs[0])
                    first_node_range = math_node_range
            case FunctionEditorMasterType.Transition:
                transition_node = tree.nodes.new('ShaderNodeGroup')
                transition_node.node_tree = utils.add_node_from_resources("reach_nodes", f"transition function type - {self.input_transition_function}")
                tree.links.new(input=first_node_input.inputs[0], output=transition_node.outputs[0])
                first_node_input = transition_node
                if self.is_ranged:
                    transition_node_range = tree.nodes.new('ShaderNodeGroup')
                    transition_node_range.node_tree = utils.add_node_from_resources("reach_nodes", f"transition function type - {self.range_transition_function}")
                    tree.links.new(input=first_node_range.inputs[0], output=transition_node_range.outputs[0])
                    first_node_range = transition_node_range
                
        if self.input:
            attribute_node = add_attribute_node(tree, self.input)
            self.input_uses_group_node = attribute_node.bl_idname == 'ShaderNodeGroup'
            if self.input in ammo_names:
                attribute_node.attribute_name = "Ammo"
                digits_node = tree.nodes.new('ShaderNodeGroup')
                digits_node.node_tree = utils.add_node_from_resources("shared_nodes", "Digits")
                tree.links.new(input=digits_node.inputs[0], output=attribute_node.outputs[2])
                tree.links.new(input=first_node_input.inputs[1] if self.master_type == FunctionEditorMasterType.Curve else first_node_input.inputs[0], output=digits_node.outputs[self.input.rpartition("_")[2].capitalize()])
            else:
                tree.links.new(input=first_node_input.inputs[1] if self.master_type == FunctionEditorMasterType.Curve else first_node_input.inputs[0], output=attribute_node.outputs[2] if attribute_node.bl_idname == 'ShaderNodeAttribute' else attribute_node.outputs[0])
            if self.is_ranged:
                attribute_node_range = add_attribute_node(tree, self.range)
                self.range_uses_group_node = attribute_node_range.bl_idname == 'ShaderNodeGroup'
                if self.range in ammo_names:
                    attribute_node_range.attribute_name = "Ammo"
                    digits_node_range = tree.nodes.new('ShaderNodeGroup')
                    digits_node_range.node_tree = utils.add_node_from_resources("shared_nodes", "Digits")
                    tree.links.new(input=digits_node_range.inputs[0], output=attribute_node_range.outputs[2])
                    tree.links.new(input=first_node_range.inputs[1] if self.master_type == FunctionEditorMasterType.Curve else first_node_range.inputs[0], output=digits_node_range.outputs[self.range.rpartition("_")[2].capitalize()])
                else:
                    tree.links.new(input=first_node_range.inputs[1] if self.master_type == FunctionEditorMasterType.Curve else first_node_range.inputs[0], output=attribute_node_range.outputs[2] if attribute_node_range.bl_idname == 'ShaderNodeAttribute' else attribute_node_range.outputs[0])
        
        if return_node_group:
            tree.links.new(input=group_output.inputs[0], output=function_node.outputs[0])
            return tree
        else:
            return function_node.outputs[0]