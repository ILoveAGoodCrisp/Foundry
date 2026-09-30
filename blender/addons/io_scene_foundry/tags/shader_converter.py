

from enum import Enum
from math import radians
import multiprocessing
from pathlib import Path
import subprocess
import time
from mathutils import Vector

from .connected_material import Function, AnimatedParameterType, FunctionEditorColorGraphType, FunctionEditorMasterType, RotateNodeInputs, TilingNodeInputs

from .render_method_option import OptionParameter

from ..constants import NormalType
from .backend import TagDocument, TagReference
from .blender import BlenderTag
from .field_view import NativeTagStruct
import os
from .bitmap import BitmapTag, bitmap_to_image
from ..tools.export_bitmaps import export_bitmap, bitmap_export_image, bitmap_needs_rebuild
from .. import utils
import bpy

from .render_method_definition import RenderMethodDefinitionTag

global_render_method_definition = None
last_group_node = None


class _EmptyReference:
    Path = None

SK_TEST_CUBEMAP = r"objects\weapons\h2a_assault_rifle\bitmaps\test_textures\sk_test_cubemap.bitmap"
DEFAULT_CUBEMAP = r"shaders\default_bitmaps\bitmaps\default_cube.bitmap"

# supports_time_period = {"shader": ("self_illum_color", "self_illum_intensity"),
#                         "shader_terrain": tuple(),
#                         "shader_custom": tuple(),
#                         "shader_decal": tuple(),
#                         "shader_foliage": tuple(),
#                         "shader_glass": tuple(),
#                         "shader_halogram": tuple(),
#                         }

srgb_names = "base_map", "palette", "self_illum_map"

def build_templates(shader_paths, do_print=False, *, from_options=False):
    new_template_count = 0
    processes = []
    max_process_count = multiprocessing.cpu_count()
    built_templates = set()
    per_template_timeout_seconds = 120

    def finish(job):
        process, template_path, started = job
        remaining = max(0, per_template_timeout_seconds - (time.perf_counter() - started))
        try:
            result = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            utils.print_warning(f"Timed out building shader template '{template_path}'. Continuing export.")
            return 0
        if result or not template_path.is_file():
            utils.print_warning(f"Failed to build shader template '{template_path}' (Tool exit code {result}).")
            return 0
        return 1
    
    if do_print: print("--- Validating templates for shaders")
    for spath in shader_paths:
        with ShaderTag(path=spath) as shader:
            path_template = shader._template_path(from_options=from_options)
            if path_template is None:
                continue
            if not path_template.exists():
                definition = shader.definition
                definition_path = shader.get_path_str(definition.Path, True)
                if definition_path and Path(definition_path).exists():
                    template_name = path_template.with_suffix("").name
                    template_key = str(path_template).casefold()
                    if template_key in built_templates:
                        continue
                    
                    built_templates.add(template_key)
                    
                    while len(processes) >= max_process_count:
                        new_template_count += finish(processes.pop(0))
                    
                    if do_print: print(f"--- Building template {template_name} for {spath}")
                    process = utils.run_tool(["generate-specified-template", "win", definition.Path.RelativePath, template_name], in_background=True, null_output=True)
                    processes.append((process, path_template, time.perf_counter()))
                    
    if do_print and processes: print("--- Waiting for Tool processes to complete")
    for job in processes:
        new_template_count += finish(job)
                    
    return new_template_count

class ChannelType(Enum):
    DEFAULT = 0
    RGB = 1
    ALPHA = 2
    RGB_ALPHA = 3

# OPTION ENUMS
class Albedo(Enum):
    DEFAULT = 0
    DETAIL_BLEND = 1
    CONSTANT_COLOR = 2
    TWO_CHANGE_COLOR = 3
    FOUR_CHANGE_COLOR = 4
    THREE_DETAIL_BLEND = 5
    TWO_DETAIL_OVERLAY = 6
    TWO_DETAIL = 7
    COLOR_MASK = 8
    TWO_DETAIL_BLACK_POINT = 9
    FOUR_CHANGE_COLOR_APPLYING_TO_SPECULAR = 10
    SIMPLE = 11
    
class BumpMapping(Enum):
    OFF = 0
    STANDARD = 1
    DETAIL = 2
    DETAIL_BLEND = 3
    THREE_DETAIL_BLEND = 4
    STANDARD_WRINKLE = 5
    DETAIL_WRINKLE = 6
    
class AlphaTest(Enum):
    NONE = 0
    SIMPLE = 1
    
class SpecularMask(Enum):
    NO_SPECULAR_MASK = 0
    SPECULAR_MASK_FROM_DIFFUSE = 1
    SPECULAR_MASK_MULT_DIFFUSE = 2
    SPECULAR_MASK_FROM_TEXTURE = 3
    
class MaterialModel(Enum):
    DIFFUSE_ONLY = 0
    COOK_TORRANCE = 1
    TWO_LOBE_PHONG = 2
    FOLIAGE = 3
    NONE = 4
    ORGANISM = 5
    HAIR = 6

class H3MaterialModel(Enum):
    DIFFUSE_ONLY = 0
    COOK_TORRANCE = 1
    TWO_LOBE_PHONG = 2
    FOLIAGE = 3
    NONE = 4
    GLASS = 5
    ORGANISM = 6
    SINGLE_LOBE_PHONG = 7
    CAR_PAINT = 8
    COOK_TORRANCE_CUSTOM_CUBE = 9
    COOK_TORRANCE_PBR_MAPS = 10
    COOK_TORRANCE_TWO_COLOR_SPEC_TINT = 11
    TWO_LOBE_PHONG_TINT_MAP = 12
    COOK_TORRANCE_SCROLLING_CUBE_MASK = 13
    COOK_TORRANCE_RIM_FRESNEL = 14
    COOK_TORRANCE_SCROLLING_CUBE = 15
    COOK_TORRANCE_FROM_ALBEDO = 16
    
class EnvironmentMapping(Enum):
    NONE = 0
    PER_PIXEL = 1
    DYNAMIC = 2
    FROM_FLAT_TEXTURE = 3
    
class SelfIllumination(Enum):
    OFF = 0
    SIMPLE = 1
    _3_CHANNEL_SELF_ILLUM = 2
    PLASMA = 3
    FROM_DIFFUSE = 4
    ILLUM_DETAIL = 5
    METER = 6
    SELF_ILLUM_TIMES_DIFFUSE = 7
    SIMPLE_WITH_ALPHA_MASK = 8
    MULTILAYER_ADDITIVE = 9
    PALETTIZED_PLASMA = 10
    CHANGE_COLOR = 11
    CHANGE_COLOR_DETAIL = 12
    
class BlendMode(Enum):
    OPAQUE = 0
    ADDITIVE = 1
    MULTIPLY = 2
    ALPHA_BLEND = 3
    DOUBLE_MULTIPLY = 4
    PRE_MULTIPLIED_ALPHA = 5
    
class Parallax(Enum):
    OFF = 0
    SIMPLE = 1
    INTERPOLATED = 2
    SIMPLE_DETAIL = 3
    
class Misc(Enum):
    DEFAULT = 0
    ROTATING_BITMAPS_SUPER_SLOW = 1

class H3Misc(Enum):
    FIRST_PERSON_NEVER = 0
    FIRST_PERSON_SOMETIMES = 1
    FIRST_PERSON_ALWAYS = 2
    FIRST_PERSON_NEVER_W_ROTATING_BITMAPS = 3
    
class Wetness(Enum):
    DEFAULT = 0
    FLOOD = 1
    PROOF = 2
    SIMPLE = 3
    RIPPLES = 4
    
class AlphaBlendSource(Enum):
    FROM_ALBEDO_ALPHA_WITHOUT_FRESNEL = 0
    FROM_ALBEDO_ALPHA = 1
    FROM_OPACITY_MAP_ALPHA = 2
    FROM_OPACITY_MAP_RGB = 3
    FROM_OPACITY_MAP_ALPHA_AND_ALBEDO_ALPHA = 4

class ShaderTag(BlenderTag, TagDocument):
    # tag_ext = 'shader'
    scale_u = 'scale x'
    scale_v = 'scale y'
    translation_u = 'translation x'
    translation_v = 'translation y'
    function_parameters = 'animated parameters'
    animated_function = 'animation function'
    color_parameter_type = 'argb color'
    self_illum_map_names = 'meter_map', 'self_illum_map'
    group_supported = True
    category_parameters = None
    category_parameters_path = None
    group_node_name = "foundry_reach.shader"
    h3_group_families = frozenset({
        'shader', 'shader_custom', 'shader_decal', 'shader_halogram',
        'shader_terrain',
    })
    group_option_start_input = 8
    palette_vector_node_name = "palettized_plasma - palette_vector"
    palette_vector_parameters = frozenset({
        "noise_map_a",
        "noise_map_b",
        "alpha_mask_map",
        "alpha_modulation_factor",
        "v_coordinate",
    })
    palette_vector_self_illumination_options = frozenset({
        "palettized_plasma",
        "palettized_plasma_change_color",
        "palettized_depth_fade",
    })
    h3_self_illumination_options = {
        9: "simple_four_change_color",
        10: "illum_detail_world_space_four_cc",
        11: "illum_change_color",
    }
    # (category_name, enum_type, option_index, group_socket_index|None)
    group_option_specs = (
        ("albedo", Albedo, 0, 0),
        ("bump_mapping", BumpMapping, 1, 1),
        ("alpha_test", AlphaTest, 2, 2),
        ("specular_mask", SpecularMask, 3, 3),
        ("material_model", MaterialModel, 4, 4),
        ("environment_mapping", EnvironmentMapping, 5, 5),
        ("self_illumination", SelfIllumination, 6, 6),
        ("blend_mode", BlendMode, 7, 7),
    )

    def __init__(self, path='', *, tag_must_exist=True, always_save=False,
                 hide_prints=False, raise_on_error=True):
        self.context = bpy.context
        self.data_dir = utils.get_data_path()
        self.always_extract_bitmaps = False
        self.unit_scale = self.context.scene.unit_settings.scale_length
        super().__init__(path, tag_must_exist=tag_must_exist,
                         always_save=always_save, hide_prints=hide_prints,
                         raise_on_error=raise_on_error)
        if self.valid:
            self._native_root = NativeTagStruct(self, self.tag.root())
            self._read_fields()
            if self.tag_is_new and not self.corinth and self.game not in {'halo1', 'halo2'}:
                self._initialize_new_shader()

    def _initialize_new_shader(self):
        definition_name = self.system_path.suffix.lstrip('.').removeprefix('shader_')
        definition_path = Path('shaders', f'{definition_name}.render_method_definition')
        with RenderMethodDefinitionTag(path=definition_path) as definition:
            option_count = len(definition.block(definition.tag.root(), 'categories'))
        if not option_count:
            raise ValueError(f'{definition_path}: render method has no categories')
        self.definition.Path = self._TagPath_from_string(definition_path)
        for _ in range(option_count):
            self.block_options.AddElement().SelectField('short').SetStringData('0')

    def _template_path(self, *, from_options=False):
        """Resolve templates even before Tool has populated a new shader's postprocess block."""
        if self.game in {'halo1', 'halo2'} or self.corinth:
            return None
        if not from_options:
            template = self._native_root.SelectField(
                'Struct:render_method[0]/Block:postprocess[0]/Reference:shader template')
            if template is not None and template.Path is not None:
                return Path(template.Path.Filename)

        definition = self.definition.Path
        if definition is None or not self.path_exists(definition):
            return None
        with RenderMethodDefinitionTag(path=definition) as document:
            option_count = len(document.block(document.tag.root(), 'categories'))
        if not option_count:
            return None
        template_name = ''.join(f'_{self._option_value_from_index(index)}' for index in range(option_count))
        definition_path = Path(definition.Filename)
        return definition_path.parent / (definition_path.stem + '_templates') / (template_name + '.render_method_template')

    def _TagPath_from_string(self, path: str | Path) -> TagReference:
        return self.reference_from_path(path)

    @staticmethod
    def get_path_str(path: TagReference | None, full_path=False) -> str:
        if path is None:
            return ''
        return path.Filename if full_path else path.RelativePathWithExtension

    def _Element_from_field_value(self, block, field_name: str, value):
        for element in block.Elements:
            field = element.SelectField(field_name)
            if field is not None and field.Value == value:
                return element
        return None

    def _Element_remove_if_needed(self, block, field_name: str, value):
        # Resolve matches before mutating the native block: deletion invalidates
        # element views and shifts every subsequent element's index.
        indices = []
        for element in block.Elements:
            field = element.SelectField(field_name)
            if field is not None and field.Value == value:
                indices.append(element.ElementIndex)
        for index in reversed(indices):
            block.RemoveElement(index)

    @staticmethod
    def _EnumIntValue(block, field_name: str, value: str) -> int | None:
        element = block.Elements[0] if block.Elements.Count else None
        field = None if element is None else element.SelectField(field_name)
        if field is None:
            return None
        target = value.casefold().replace('_', ' ')
        for index, item in enumerate(field.Items):
            if item.EnumName.casefold().replace('_', ' ') == target:
                return index
        return None

    @staticmethod
    def _FunctionEditorColorGraphType(value: int) -> int:
        return value

    @staticmethod
    def _FunctionEditorMasterType(value: int) -> int:
        return value

    @staticmethod
    def _GameColor_from_RGB(red: float, green: float, blue: float,
                            alpha: float = 1.0):
        from .field_view import NativeGameColor
        return NativeGameColor(red, green, blue, alpha)
    
    def _read_fields(self):
        if self.game in {'halo1', 'halo2'}:
            self.reference = _EmptyReference()
            self.definition = _EmptyReference()
            self.block_parameters = None
            self.block_options = None
            return
        self.render_method = self._native_root.SelectField("Struct:render_method").Elements[0]
        self.block_parameters = self.render_method.SelectField("parameters")
        self.block_options = self.render_method.SelectField('options')
        self.reference = self.render_method.SelectField('reference') or _EmptyReference()
        if self.reference.Path and self.reference.Path == self.tag_path: # prevent recursion issues
            self.reference.Path = None
        self.definition = self.render_method.SelectField('definition')
        
    def get_global_material(self):
        global_material_field = self._native_root.SelectField("StringId:material name")
        if global_material_field is None:
            global_material_field = self._native_root.SelectField("StringId:material name 0")
            
        if global_material_field is None:
            return ""
            
        global_material = global_material_field.GetStringData()
        
        if not global_material and self.reference.Path is not None and self.path_exists(self.reference.Path):
            with ShaderTag(path=self.reference.Path) as ref_shader:
                return ref_shader.get_global_material()
        
        return global_material
    
    @classmethod
    def _get_info(cls, definition_path: TagReference):
        definition_key = cls.get_path_str(definition_path, True)
        if cls.category_parameters is not None and cls.category_parameters_path == definition_key:
            return
        if definition_path is None:
            cls.category_parameters = {}
        else:
            with RenderMethodDefinitionTag(path=definition_path) as render_method_definition:
                cls.category_parameters = render_method_definition.get_defaults()
        cls.category_parameters_path = definition_key
                
    def get_albedo_bitmap(self):
        for element in self.block_parameters.Elements:
            if element.Fields[0].GetStringData() == 'base_map':
                bitmap = element.SelectField("Reference:bitmap").Path
                if self.path_exists(bitmap):
                    return bitmap
                
    def is_opaque(self):
        e_alpha_test = AlphaTest(self._option_value_from_index(2))
        e_blend_mode = BlendMode(self._option_value_from_index(7))
        
        return e_alpha_test.value == 0 and e_blend_mode.value == 0
    
    def write_tag(self, blender_material, linked_to_blender, material_shader=''):
        self.blender_material = blender_material
        self.material_shader = material_shader
        self.group_node = self._find_group_node(blender_material)
        if self.corinth:
            self.custom = self.group_node is not None
        else:
            self.custom = self._group_node_matches(self.group_node)
        if linked_to_blender:
            self._edit_tag()
        elif self.corinth and self.material_shader:
            self._native_root.SelectField("Reference:material shader").Path = self._TagPath_from_string(self.material_shader)
            
        return self.tag_path.RelativePathWithExtension
        
    def _edit_tag(self):
        self.alpha_type = self._alpha_type_from_blender_material()
        used_group_export = bool(self.custom and self._from_nodes_group())
        if not used_group_export:
            self._build_basic(self._get_basic_mapping(self.blender_material))
        
        self.tag_has_changes = True

    def _iter_material_output_surface_links(self, node_tree: bpy.types.NodeTree):
        for node in node_tree.nodes:
            if node.type != "OUTPUT_MATERIAL":
                continue
            surface_input = node.inputs.get('Surface')
            if surface_input is None and node.inputs:
                surface_input = node.inputs[0]
            if surface_input is None:
                continue
            for link in surface_input.links:
                yield link

    def _iter_upstream_nodes_from_material_outputs(self, node_tree: bpy.types.NodeTree):
        pending = [link.from_node for link in self._iter_material_output_surface_links(node_tree)]
        visited = set()
        while pending:
            node = pending.pop(0)
            if node is None or id(node) in visited:
                continue
            visited.add(id(node))
            yield node
            for input_socket in node.inputs:
                for link in input_socket.links:
                    pending.append(link.from_node)

    def _group_node_is_export_candidate(self, group_node: bpy.types.Node | None) -> bool:
        return self._group_node_matches(group_node)

    def _find_group_node(self, blender_material: bpy.types.Material) -> bpy.types.Node | None:
        tree = blender_material.node_tree
        if tree is None:
            return

        for node in self._iter_upstream_nodes_from_material_outputs(tree):
            if node.type == "GROUP" and getattr(node, "node_tree", None) and self._group_node_is_export_candidate(node):
                return node

        for node in tree.nodes:
            if node.type == "GROUP" and getattr(node, "node_tree", None) and self._group_node_is_export_candidate(node):
                return node

        for link in self._iter_material_output_surface_links(tree):
            from_node = link.from_node
            if from_node.type == "GROUP" and getattr(from_node, "node_tree", None):
                return from_node

        return None

    @staticmethod
    def _normalize_group_name(name: str) -> str:
        if not name:
            return ""

        normalized = name.lower().replace(" ", "_")
        # Blender appends numeric copy suffixes like ".001" to datablock names.
        # Strip only numeric suffixes so semantic shader suffixes (e.g. ".shader")
        # are preserved for matching.
        base, sep, suffix = normalized.rpartition(".")
        if sep and suffix.isdigit():
            return base
        return normalized

    def _group_node_matches(self, group_node: bpy.types.Node | None) -> bool:
        if group_node is None or group_node.type != "GROUP":
            return False
        group_tree = getattr(group_node, "node_tree", None)
        if group_tree is None:
            return False

        group_name = self._normalize_group_name(group_tree.name)
        expected = self.group_node_name
        if self.game in {'halo3', 'halo3odst'}:
            family = self.system_path.suffix.lstrip('.').casefold()
            if family in self.h3_group_families:
                expected = f'foundry_h3.{family}'
        if isinstance(expected, str):
            return group_name == expected
        return group_name in expected

    def _group_option_member_from_socket(self, category_name: str, enum_cls: type[Enum], socket_value):
        if socket_value is None:
            return None
        if isinstance(socket_value, str):
            wanted = utils.game_str(socket_value)
            for member in enum_cls:
                if self._group_option_key(category_name, member) == wanted:
                    return member
            return None

        try:
            return enum_cls(int(socket_value))
        except Exception:
            return None

    def _group_option_member_from_tag(self, enum_cls: type[Enum], option_index: int):
        # Export-time fallback should remain local to this tag to avoid
        # reference-chain recursion loops on malformed/cyclic tag references.
        try:
            option_data = int(self.block_options.Elements[option_index].Fields[0].Data)
            if option_data >= 0:
                return enum_cls(option_data)
        except Exception:
            pass

        try:
            return next(iter(enum_cls))
        except Exception:
            return None

    def _group_option_key(self, category_name: str, enum_member: Enum) -> str:
        if self.game in {'halo3', 'halo3odst'} and category_name == 'self_illumination':
            return self.h3_self_illumination_options.get(enum_member.value, utils.game_str(enum_member.name))
        return utils.game_str(enum_member.name)

    def _self_illumination_uses_palette_vector(self, self_illumination) -> bool:
        if isinstance(self_illumination, Enum):
            self_illumination = self_illumination.name
        return utils.game_str(str(self_illumination)) in self.palette_vector_self_illumination_options

    def _find_palette_vector_node(self) -> bpy.types.Node | None:
        if self.group_node is None:
            return None

        palette_input = self.group_node.inputs.get("palette.rgb")
        if palette_input is None:
            palette_input = self.group_node.inputs.get("palette")
        if palette_input is None:
            return None

        palette_node = utils.find_linked_node(self.group_node, palette_input.name.lower(), "TEX_IMAGE")
        if palette_node is None:
            return None

        vector_input = palette_node.inputs.get("Vector")
        if vector_input is None:
            return None

        wanted_name = self._normalize_group_name(self.palette_vector_node_name)
        pending = [link.from_node for link in vector_input.links]
        visited = set()
        while pending:
            node = pending.pop(0)
            if node is None or id(node) in visited:
                continue
            visited.add(id(node))

            if node.type == "GROUP" and getattr(node, "node_tree", None):
                if self._normalize_group_name(node.node_tree.name) == wanted_name:
                    return node

            for input_socket in node.inputs:
                pending.extend(link.from_node for link in input_socket.links)

        return None

    def _apply_group_options_from_node(self) -> dict[str, str]:
        selected = {}
        inputs = list(self.group_node.inputs)
        for category_name, enum_cls, option_index, socket_index in self.group_option_specs:
            if enum_cls is MaterialModel and self.game in {'halo3', 'halo3odst'}:
                enum_cls = H3MaterialModel
            enum_member = None
            if socket_index is not None and socket_index < len(inputs):
                enum_member = self._group_option_member_from_socket(
                    category_name, enum_cls, inputs[socket_index].default_value
                )
            if enum_member is None:
                enum_member = self._group_option_member_from_tag(enum_cls, option_index)
            if enum_member is None:
                return {}

            try:
                option_field = self.block_options.Elements[option_index].SelectField("short")
                option_field.SetStringData(str(int(enum_member.value)))
            except Exception:
                pass

            selected[category_name] = self._group_option_key(category_name, enum_member)

        return selected

    def _parameter_type_tokens(self, parameter: OptionParameter):
        try:
            parameter_type = ParameterType(parameter.type)
        except Exception:
            return None

        match parameter_type:
            case ParameterType.BITMAP:
                return "bitmap", "bitmap"
            case ParameterType.COLOR | ParameterType.ARGB_COLOR:
                return "color", self.color_parameter_type
            case ParameterType.REAL:
                return "real", "real"
            case ParameterType.INT:
                return "int", "int"
            case ParameterType.BOOL:
                return "bool", "bool"
            case _:
                return None

    def _from_nodes_group(self) -> bool:
        if self.group_node is None or not self._group_node_matches(self.group_node):
            return False

        self._get_info(self.definition.Path)
        if not self.category_parameters:
            utils.print_warning(
                f"Could not load reach shader category defaults for '{self.tag_path.RelativePathWithExtension}'. "
                "Falling back to adaptive basic mapping"
            )
            return False

        selected_options = self._apply_group_options_from_node()
        if not selected_options:
            utils.print_warning(
                f"Could not read reach shader option selections from node group '{self.group_node.node_tree.name}'. "
                "Falling back to adaptive basic mapping"
            )
            return False

        self.shader_parameters = {}
        for category_name, option_name in selected_options.items():
            category = self.category_parameters.get(category_name)
            if not category:
                wanted_category = utils.game_str(category_name)
                for k, v in self.category_parameters.items():
                    if utils.game_str(k) == wanted_category:
                        category = v
                        break
                if not category:
                    utils.print_warning(
                        f"Missing reach shader category '{category_name}'. Falling back to adaptive basic mapping"
                    )
                    return False

            option_parameters = category.get(option_name)
            if option_parameters is None:
                wanted = utils.game_str(option_name)
                for k, v in category.items():
                    if utils.game_str(k) == wanted:
                        option_parameters = v
                        break

            if option_parameters is None:
                utils.print_warning(
                    f"Missing reach shader option '{option_name}' in category '{category_name}'. Falling back to adaptive basic mapping"
                )
                return False

            self.shader_parameters.update(option_parameters)

        self.true_parameters = {option.ui_name: option for option in self.shader_parameters.values()}

        alias_map: dict[str, tuple[str, OptionParameter]] = {}
        cull_chars = " _-()'\""
        for parameter_name, parameter in self.shader_parameters.items():
            for alias in (parameter_name, parameter.ui_name):
                if not alias:
                    continue
                key = utils.remove_chars(alias.lower(), cull_chars)
                if key and key not in alias_map:
                    alias_map[key] = (parameter_name, parameter)
        palette_vector_node = None

        parameter_nodes = []
        if self._self_illumination_uses_palette_vector(selected_options.get("self_illumination", "")):
            palette_vector_node = self._find_palette_vector_node()
            if palette_vector_node is not None:
                parameter_nodes.append((palette_vector_node, list(palette_vector_node.inputs)))

        inputs = list(self.group_node.inputs)
        parameter_nodes.append((self.group_node, inputs[self.group_option_start_input:]))

        seen_parameters = set()
        for source_node, input_sockets in parameter_nodes:
            for input_socket in input_sockets:
                input_base_name = input_socket.name.partition(".")[0]
                if (source_node is self.group_node and palette_vector_node is not None
                        and input_base_name.lower() in self.palette_vector_parameters):
                    continue

                key = utils.remove_chars(input_base_name.lower(), cull_chars)
                match = alias_map.get(key)
                if match is None:
                    continue

                parameter_name, parameter = match
                if parameter_name in seen_parameters:
                    continue

                type_tokens = self._parameter_type_tokens(parameter)
                if type_tokens is None:
                    continue
                source_type, tag_type = type_tokens

                source = self._source_from_input_and_parameter_type(input_socket, source_type, source_node)
                if source is None:
                    continue

                element = self._setup_parameter(source, parameter_name, tag_type)
                if element:
                    self._setup_function_parameters(source, element, source_type)
                    seen_parameters.add(parameter_name)

        return True
    
    def _get_basic_mapping(self, blender_material):
        """Best-effort mapping from arbitrary Blender node trees to basic Halo shader properties."""
        maps = {}
        node_tree = blender_material.node_tree
        if not node_tree or not node_tree.nodes:
            albedo_tint = utils.get_material_albedo(blender_material)
            if albedo_tint:
                maps['albedo_tint'] = albedo_tint
            return maps
        
        property_keys = ('diffuse', 'specular', 'normal', 'self_illum', 'alpha')
        zero_scores = {k: 0.0 for k in property_keys}
        property_hits = {k: [] for k in property_keys}
        shader_hits = {}
        traversal_guard = set()
        node_output_visits = {}
        max_walk_depth = 128
        max_walk_visits = 12000
        max_node_output_visits = 24
        walk_aborted = False
        hit_order = 0
        
        def _norm(text) -> str:
            if not text:
                return ''
            return ''.join(c if (c.isalnum() or c.isspace()) else ' ' for c in str(text).lower()).strip()
        
        def _merge_scores(base: dict, delta: dict) -> dict:
            merged = base.copy()
            for k, v in delta.items():
                merged[k] = merged.get(k, 0.0) + v
            return merged
        
        def _scores_from_input(node: bpy.types.Node, input_socket: bpy.types.NodeSocket) -> dict:
            text = _norm(input_socket.name)
            tokens = set(text.split())
            score = {k: 0.0 for k in property_keys}
            
            if 'base color' in text or 'albedo' in text or 'diffuse' in text:
                score['diffuse'] += 10.0
            elif text == 'color' or text.endswith(' color'):
                score['diffuse'] += 3.0
            
            if 'al' in tokens:
                score['diffuse'] += 15.0
            if 'sp' in tokens:
                score['specular'] += 12.0
            if 'nm' in tokens:
                score['normal'] += 16.0
            if 'em' in tokens:
                score['self_illum'] += 16.0
            if 'pm' in tokens:
                score['diffuse'] -= 12.0
                score['specular'] += 6.0
                score['alpha'] += 3.0
            
            if 'specular' in text or 'rough' in text or 'metal' in text or 'gloss' in text or 'ior' in text or 'reflect' in text:
                score['specular'] += 8.0
            if 'normal' in text or 'bump' in text or 'height' in text or 'tangent' in text:
                score['normal'] += 11.0
            if 'emission' in text or 'emissive' in text or 'self illum' in text or 'glow' in text:
                score['self_illum'] += 11.0
            if 'alpha' in text or 'opacity' in text or 'transparen' in text or 'cutout' in text or 'mask' in text:
                score['alpha'] += 9.0
            
            match node.type:
                case 'BSDF_PRINCIPLED':
                    if 'base color' in text:
                        score['diffuse'] += 18.0
                    if 'specular' in text:
                        score['specular'] += 18.0
                    if text == 'normal':
                        score['normal'] += 20.0
                    if 'emission' in text:
                        score['self_illum'] += 20.0
                    if text == 'alpha':
                        score['alpha'] += 20.0
                case 'NORMAL_MAP' | 'BUMP':
                    score['normal'] += 12.0
                case 'EMISSION':
                    score['self_illum'] += 12.0
                case 'MIX_SHADER' | 'MIX_RGB' | 'MIX':
                    if text in {'fac', 'factor'}:
                        score['alpha'] += 5.0
            
            return score
        
        def _scores_from_node(node: bpy.types.Node) -> dict:
            score = {k: 0.0 for k in property_keys}
            match node.type:
                case 'NORMAL_MAP' | 'BUMP':
                    score['normal'] += 6.0
                case 'EMISSION':
                    score['self_illum'] += 6.0
                case 'BSDF_PRINCIPLED':
                    score['diffuse'] += 1.0
                    score['specular'] += 1.0
                    score['normal'] += 1.0
                    score['self_illum'] += 1.0
            return score
        
        def _scores_from_output(output_name: str) -> dict:
            text = _norm(output_name)
            score = {k: 0.0 for k in property_keys}
            if text == 'alpha':
                score['alpha'] += 7.0
                score['specular'] += 2.0
                score['self_illum'] += 2.0
            if text in {'color', 'rgb'}:
                score['diffuse'] += 1.0
            if 'normal' in text:
                score['normal'] += 6.0
            return score
        
        def _scores_from_texture_name(node: bpy.types.Node) -> dict:
            score = {k: 0.0 for k in property_keys}
            image = getattr(node, 'image', None)
            name_bits = [node.name, node.label]
            if image:
                name_bits.append(image.name)
                if image.filepath:
                    name_bits.append(Path(image.filepath).stem)
            text = _norm(' '.join(filter(None, name_bits)))
            tokens = set(text.split())
            compact = ''.join(tokens)
            
            if tokens.intersection({'albedo', 'diffuse', 'basecolor', 'base', 'color', 'col', 'bc', 'al'}) or 'basecolor' in compact:
                score['diffuse'] += 6.0
            if tokens.intersection({'spec', 'specular', 'rough', 'roughness', 'metal', 'metallic', 'gloss', 'orm', 'rma', 'mra', 'sp'}):
                score['specular'] += 6.0
            if tokens.intersection({'normal', 'nrm', 'norm', 'nm', 'bump', 'height'}):
                score['normal'] += 8.0
            if tokens.intersection({'emissive', 'emission', 'emit', 'glow', 'selfillum', 'illum', 'si', 'em'}):
                score['self_illum'] += 8.0
            if tokens.intersection({'alpha', 'opacity', 'mask', 'cutout', 'transparency', 'trans'}):
                score['alpha'] += 7.0
            
            # Packed maps are commonly not albedo; keep them away from diffuse unless no better candidate exists.
            if 'pm' in tokens:
                score['diffuse'] -= 10.0
                score['specular'] += 5.0
                score['alpha'] += 2.0
            
            if image and image.colorspace_settings:
                color_space = image.colorspace_settings.name.lower()
                if 'non' in color_space:
                    score['diffuse'] -= 1.5
                    score['normal'] += 1.0
                    score['specular'] += 1.0
                    score['alpha'] += 0.5
            
            return score
        
        def _channel_tags(node: bpy.types.Node, output_name='') -> set[str]:
            image = getattr(node, 'image', None)
            name_bits = [node.name, node.label, output_name]
            if image:
                name_bits.append(image.name)
                if image.filepath:
                    name_bits.append(Path(image.filepath).stem)
            text = _norm(' '.join(filter(None, name_bits)))
            return set(text.split())
        
        def _register_shader(node: bpy.types.Node, path_scores: dict, distance: int):
            if not node.type.startswith('BSDF'):
                return
            node_id = id(node)
            input_names = {_norm(i.name) for i in node.inputs}
            score = 0.0
            if node.type == 'BSDF_PRINCIPLED':
                score += 40.0
            else:
                score += 22.0
            if 'base color' in input_names or 'color' in input_names:
                score += 5.0
            if any('normal' in name for name in input_names):
                score += 5.0
            if any('emission' in name for name in input_names):
                score += 5.0
            score += max(0.0, 16.0 - distance)
            score += path_scores.get('diffuse', 0.0) * 0.25
            score += path_scores.get('normal', 0.0) * 0.25
            score += path_scores.get('self_illum', 0.0) * 0.25
            
            previous = shader_hits.get(node_id)
            if previous is None or score > previous['score']:
                shader_hits[node_id] = {'node': node, 'score': score, 'distance': distance}
        
        def _register_image(node: bpy.types.Node, path_scores: dict, output_name: str, distance: int):
            nonlocal hit_order
            output_name = _norm(output_name)
            score = _merge_scores(path_scores, _scores_from_texture_name(node))
            score = _merge_scores(score, _scores_from_output(output_name))
            tags = _channel_tags(node, output_name)
            distance_bias = max(0.0, 4.0 - float(min(distance, 4)))
            has_image = bool(getattr(node, 'image', None))
            for key in property_keys:
                final_score = score[key] + distance_bias * (0.25 if key != 'alpha' else 0.1)
                if final_score <= 0.0:
                    continue
                property_hits[key].append(
                    {
                        'node': node,
                        'score': final_score,
                        'distance': distance,
                        'output_name': output_name,
                        'has_image': has_image,
                        'tags': tags,
                        'order': hit_order,
                    }
                )
            
            hit_order += 1
        
        def _walk(node: bpy.types.Node, output_name='', group_stack=(), path_scores=None, distance=0):
            nonlocal walk_aborted
            if node is None:
                return
            if walk_aborted:
                return
            if distance > max_walk_depth:
                return
            if path_scores is None:
                path_scores = zero_scores
            
            output_norm = _norm(output_name)

            node_output_key = (id(node), output_norm)
            visits = node_output_visits.get(node_output_key, 0)
            if visits >= max_node_output_visits:
                return
            node_output_visits[node_output_key] = visits + 1

            # Keep only immediate group context to avoid runaway state growth in cyclic
            # group-input/group-output graphs while preserving local traversal behavior.
            context_group = id(group_stack[-1]) if group_stack else 0
            guard_key = (id(node), output_norm, context_group)
            if guard_key in traversal_guard:
                return
            if len(traversal_guard) >= max_walk_visits:
                walk_aborted = True
                return
            traversal_guard.add(guard_key)
            
            current_scores = _merge_scores(path_scores, _scores_from_node(node))
            _register_shader(node, current_scores, distance)
            
            if node.type == 'TEX_IMAGE':
                _register_image(node, current_scores, output_name, distance)
            
            if node.type == 'GROUP_INPUT':
                if group_stack:
                    parent_group = group_stack[-1]
                    parent_inputs = []
                    if output_norm:
                        for parent_input in parent_group.inputs:
                            if _norm(parent_input.name) == output_norm:
                                parent_inputs.append(parent_input)
                    if not parent_inputs and output_norm:
                        output_tokens = set(output_norm.split())
                        for parent_input in parent_group.inputs:
                            parent_tokens = set(_norm(parent_input.name).split())
                            if output_tokens and output_tokens.intersection(parent_tokens):
                                parent_inputs.append(parent_input)
                    if not parent_inputs:
                        linked_inputs = [parent_input for parent_input in parent_group.inputs if parent_input.links]
                        if not output_norm:
                            parent_inputs = linked_inputs
                        elif len(linked_inputs) == 1:
                            parent_inputs = linked_inputs
                        else:
                            return
                    
                    for parent_input in parent_inputs:
                        edge_scores = _scores_from_input(parent_group, parent_input)
                        next_scores = _merge_scores(current_scores, edge_scores)
                        for link in parent_input.links:
                            _walk(link.from_node, link.from_socket.name, group_stack[:-1], next_scores, distance + 1)
                return
            
            if node.type == 'GROUP' and node.node_tree:
                traversed_internal = False
                group_outputs = [n for n in node.node_tree.nodes if n.type == 'GROUP_OUTPUT']
                for group_output in group_outputs:
                    for group_input in group_output.inputs:
                        if output_norm and _norm(group_input.name) != output_norm:
                            continue
                        edge_scores = _scores_from_input(group_output, group_input)
                        next_scores = _merge_scores(current_scores, edge_scores)
                        for link in group_input.links:
                            traversed_internal = True
                            _walk(link.from_node, link.from_socket.name, group_stack + (node,), next_scores, distance + 1)
                if traversed_internal:
                    return
            
            for input_socket in node.inputs:
                if not input_socket.links:
                    continue
                edge_scores = _scores_from_input(node, input_socket)
                next_scores = _merge_scores(current_scores, edge_scores)
                for link in input_socket.links:
                    _walk(link.from_node, link.from_socket.name, group_stack, next_scores, distance + 1)
        
        surface_links = []
        for output_node in node_tree.nodes:
            if output_node.type != 'OUTPUT_MATERIAL':
                continue
            surface_input = output_node.inputs.get('Surface')
            if surface_input is None and output_node.inputs:
                surface_input = output_node.inputs[0]
            if not surface_input or not surface_input.links:
                continue
            for link in surface_input.links:
                surface_links.append((surface_input, link))
        
        for surface_input, link in surface_links:
            seed_scores = _scores_from_input(surface_input.node, surface_input)
            _walk(link.from_node, link.from_socket.name, tuple(), seed_scores, 0)

        if walk_aborted:
            utils.print_warning(
                "Adaptive shader-node mapping traversal reached safety limits and was truncated to avoid infinite recursion"
            )
        
        if not any(property_hits.values()):
            for node in node_tree.nodes:
                _register_shader(node, zero_scores, 32)
                if node.type == 'TEX_IMAGE':
                    _register_image(node, zero_scores, '', 32)
        
        bsdf_node = None
        if shader_hits:
            best_shader = sorted(
                shader_hits.values(),
                key=lambda hit: (-hit['score'], hit['distance'], hit['node'].name),
            )[0]
            bsdf_node = best_shader['node']
        else:
            bsdf_node = utils.get_blender_shader(node_tree)
        
        mapping_root = bsdf_node
        if mapping_root is None and surface_links:
            mapping_root = surface_links[0][1].from_node
        if mapping_root:
            maps['mapping_root'] = mapping_root
            maps['bsdf'] = bsdf_node if bsdf_node else mapping_root
        elif bsdf_node:
            maps['bsdf'] = bsdf_node
        
        def _pick_best(prop_name: str, minimum_score: float):
            hits = property_hits[prop_name]
            if not hits:
                return None, None
            ranked = sorted(
                hits,
                key=lambda hit: (-hit['score'], -int(hit['has_image']), hit['distance'], hit['order']),
            )
            
            preferred_tags_by_property = {
                'diffuse': {'al', 'albedo', 'diffuse', 'basecolor', 'base', 'bc'},
                'specular': {'sp', 'spec', 'specular', 'rough', 'metal', 'gloss', 'orm', 'rma', 'mra', 'pm'},
                'normal': {'nm', 'normal', 'nrm', 'norm', 'bump', 'height'},
                'self_illum': {'em', 'emissive', 'emission', 'selfillum', 'illum', 'glow', 'si'},
                'alpha': {'alpha', 'opacity', 'mask', 'cutout', 'transparency', 'trans'},
            }
            avoid_tags_by_property = {
                'diffuse': {'pm', 'sp', 'nm', 'em'},
            }
            
            preferred_tags = preferred_tags_by_property.get(prop_name, set())
            avoid_tags = avoid_tags_by_property.get(prop_name, set())
            
            preferred_hits = [hit for hit in ranked if preferred_tags.intersection(hit.get('tags', set()))]
            if preferred_hits:
                ranked = preferred_hits
            
            if avoid_tags:
                non_avoided_hits = [hit for hit in ranked if not avoid_tags.intersection(hit.get('tags', set()))]
                if non_avoided_hits:
                    ranked = non_avoided_hits
            
            for hit in ranked:
                if hit['score'] >= minimum_score:
                    return hit['node'], hit
            return ranked[0]['node'], ranked[0]
        
        thresholds = {
            'diffuse': 2.0,
            'specular': 3.5,
            'normal': 4.0,
            'self_illum': 4.0,
            'alpha': 3.0,
        }
        chosen_hits = {}
        for key in property_keys:
            node, hit = _pick_best(key, thresholds[key])
            if node:
                maps[key] = node
                chosen_hits[key] = hit
        
        # Direct-input fallback when the heuristic pass couldn't resolve an expected slot.
        fallback_shader = bsdf_node if bsdf_node else maps.get('mapping_root')
        if fallback_shader:
            fallback_inputs = {
                'diffuse': 'base color',
                'specular': 'specular ior level',
                'normal': 'normal',
                'self_illum': 'emission color',
                'alpha': 'alpha',
            }
            for key, input_name in fallback_inputs.items():
                if key in maps:
                    continue
                node = utils.find_linked_node(fallback_shader, input_name, 'TEX_IMAGE')
                if node:
                    maps[key] = node
        
        diffuse_hit = chosen_hits.get('diffuse')
        spec_hit = chosen_hits.get('specular')
        if diffuse_hit and spec_hit and spec_hit['node'] == diffuse_hit['node'] and spec_hit['output_name'] == 'alpha':
            maps['specular_from_diffuse_alpha'] = True
        
        self_illum_hit = chosen_hits.get('self_illum')
        if diffuse_hit and self_illum_hit and self_illum_hit['node'] == diffuse_hit['node'] and self_illum_hit['output_name'] == 'alpha':
            maps['self_illum_from_diffuse_alpha'] = True
        
        if bsdf_node:
            emission_input = bsdf_node.inputs.get('Emission Strength')
            if emission_input is None:
                for input_socket in bsdf_node.inputs:
                    if _norm(input_socket.name) == 'emission strength':
                        emission_input = input_socket
                        break
            if emission_input:
                try:
                    maps['emission_strength'] = float(emission_input.default_value)
                except (TypeError, ValueError):
                    pass
        
        if maps.get('diffuse') is None:
            if bsdf_node:
                albedo_tint = utils.get_material_albedo(bsdf_node)
                if albedo_tint:
                    maps['albedo_tint'] = albedo_tint
            if maps.get('albedo_tint') is None:
                albedo_tint = utils.get_material_albedo(blender_material)
                if albedo_tint:
                    maps['albedo_tint'] = albedo_tint
        
        return maps
        
    def _alpha_type_from_blender_material(self):
        if self.blender_material.surface_render_method == 'DITHERED':
                return ''
            
        return 'blend'
            
    def _build_basic(self, map: dict):
        self.group_node = map.get("mapping_root") or map.get("bsdf")
        albedo = self.block_options.Elements[0].SelectField('short')
        bump_mapping = self.block_options.Elements[1].SelectField('short')
        alpha_test = self.block_options.Elements[2].SelectField('short')
        specular_mask = self.block_options.Elements[3].SelectField('short')
        self_illumination = self.block_options.Elements[6].SelectField('short')
        blend_mode = self.block_options.Elements[7].SelectField('short')
        alpha_blend_source = (self.block_options.Elements[11].SelectField('short')
                              if self.game == 'reach' else None)
        # Set up shader parameters
        spec_alpha_from_diffuse = bool(map.get('specular_from_diffuse_alpha'))
        si_alpha_from_diffuse = bool(map.get('self_illum_from_diffuse_alpha'))
        if map.get('diffuse', 0):
            if int(albedo.GetStringData()) == 2 or int(albedo.GetStringData()) == -1: # if is constant color or none
                albedo.SetStringData('0') # sets default
            element = self._setup_parameter(map['diffuse'], 'base_map', 'bitmap')
            if element:
                self._setup_function_parameters(map['diffuse'], element, 'bitmap')
                diff_alpha_output = map['diffuse'].outputs.get('Alpha')
                if diff_alpha_output is None and len(map['diffuse'].outputs) > 1:
                    diff_alpha_output = map['diffuse'].outputs[1]
                if diff_alpha_output and diff_alpha_output.links:
                    for l in diff_alpha_output.links:
                        if l.to_socket.name.lower() == 'specular ior level':
                            spec_alpha_from_diffuse = True
                        if l.to_socket.name.lower() == 'emission color':
                            si_alpha_from_diffuse = True
                
        elif map.get('albedo_tint', 0):
            albedo.SetStringData('2') # constant color
            element = self._setup_parameter(map['albedo_tint'], 'albedo_color', self.color_parameter_type)
            if element:
                self._setup_function_parameters(map['albedo_tint'], element, 'color')
                
        if spec_alpha_from_diffuse:
            specular_mask.SetStringData('1') # Specular mask from diffuse
        elif map.get('specular', 0):
            specular_mask.SetStringData('3') # Specular mask from texture
            element = self._setup_parameter(map['specular'], 'specular_mask_texture', 'bitmap')
            if element:
                self._setup_function_parameters(map['specular'], element, 'bitmap')
        else:
            specular_mask.SetStringData('-1')
            
        if si_alpha_from_diffuse:
            self_illumination.SetStringData('4') # self illum mask from diffuse
        elif map.get('self_illum', 0):
            si_enum = int(self_illumination.GetStringData())
            if si_enum < 1 or si_enum == 4:
                self_illumination.SetStringData('1') # simple
            element = self._setup_parameter(map['self_illum'], 'self_illum_map', 'bitmap')
            if element:
                self._setup_function_parameters(map['self_illum'], element, 'bitmap')
                
        if si_alpha_from_diffuse or map.get('self_illum', 0):
            si_intensity = map.get('emission_strength')
            if si_intensity is None:
                bsdf = map.get('bsdf')
                emission_input = None
                if bsdf and hasattr(bsdf, 'inputs'):
                    emission_input = bsdf.inputs.get('Emission Strength')
                    if emission_input is None:
                        for input_socket in bsdf.inputs:
                            if input_socket.name.lower() == 'emission strength':
                                emission_input = input_socket
                                break
                if emission_input:
                    si_intensity = emission_input.default_value
                else:
                    si_intensity = 1
            element = self._setup_parameter(si_intensity, 'self_illum_intensity', 'real')
            if element:
                self._setup_function_parameters(si_intensity, element, 'real')
        else:
            self_illumination.SetStringData('-1')
            
        if map.get('normal', 0):
            if int(bump_mapping.GetStringData()) < 1:
                bump_mapping.SetStringData('1') # standard
            element = self._setup_parameter(map['normal'], 'bump_map', 'bitmap')
            if element:
                self._setup_function_parameters(map['normal'], element, 'bitmap')
        elif int(bump_mapping.GetStringData()) > 0:
            bump_mapping.SetStringData('-1') # none
            
        if self.alpha_type == 'clip' and map.get('alpha', 0):
            alpha_test.SetStringData('1')
            element = self._setup_parameter(map['alpha'], 'alpha_test_map', 'bitmap')
            if element:
                self._setup_function_parameters(map['alpha'], element, 'bitmap')
        elif self.alpha_type == 'blend':
            alpha_test.SetStringData('-1')
            if int(blend_mode.GetStringData()) < 1:
                blend_mode.SetStringData('3')
            if map.get('alpha', 0):
                if alpha_blend_source is not None and int(alpha_blend_source.GetStringData()) != 4:
                    alpha_blend_source.SetStringData('3') if map.get('alpha').inputs[0].links else alpha_blend_source.SetStringData('2')
                element = self._setup_parameter(map['alpha'], 'opacity_map', 'bitmap')
                if element:
                    self._setup_function_parameters(map['alpha'], element, 'bitmap')
        else:
            alpha_test.SetStringData('-1')
            blend_mode.SetStringData('-1')
            if alpha_blend_source is not None:
                alpha_blend_source.SetStringData('-1')
          
    def _setup_parameter(self, source, parameter_name, parameter_type):
        element = self._Element_from_field_value(self.block_parameters, 'parameter name', parameter_name)
        if element is None:
            element = self.block_parameters.AddElement()
            element.SelectField('parameter name').SetStringData(parameter_name)
            element.SelectField('parameter type').SetValue(parameter_type)
        match parameter_type:
            case 'bitmap':
                bitmap_path = self._get_bitmap_path(source)
                if bitmap_path:
                    element.SelectField('bitmap flags').SetStringData('1') # sets override
                    element.SelectField('bitmap filter mode').SetStringData('6') # sets anisotropic (4) EXPENSIVE
                    element.SelectField('bitmap').Path = self._TagPath_from_string(bitmap_path)
                else:
                    element.SelectField('bitmap').Path = None
                    return 
                    
            case 'real':
                element.SelectField('real').SetStringData(str(source))
            case 'int':
                element.SelectField('int\\bool').SetStringData(str(source))
            case 'bool':
                element.SelectField('int\\bool').SetStringData(str(source))
                
        return element
    
    def _get_bitmap_path(self, node):
        if not hasattr(node, 'image'):
            return
        image = node.image
        if not image:
            return
        image = bitmap_export_image(image)
        if bitmap_needs_rebuild(image):
            bitmap = export_bitmap(image)
            if bitmap and Path(self.tags_dir, bitmap).exists():
                return bitmap
            return
        nwo = image.nwo
        if nwo.filepath:
            bitmap = str(Path(nwo.filepath).with_suffix(".bitmap"))
            if Path(self.tags_dir, bitmap).exists():
                return bitmap
            
        if image.filepath and Path(image.filepath_from_user()).exists() and Path(image.filepath_from_user()).is_relative_to(Path(self.data_dir)):
            bitmap = str(Path(image.filepath_from_user()).relative_to(Path(self.data_dir)).with_suffix(".bitmap"))
            if Path(self.tags_dir, bitmap).exists():
                return bitmap

        bitmap = export_bitmap(image)
        if not bitmap:
            return
        if Path(self.tags_dir, bitmap).exists():
            return bitmap
    
    def _function_parameters_from_node(self, source, parameter_type):
        mapping = {}
        match parameter_type:
            case 'bitmap':
                if isinstance(source, bpy.types.Node):
                    if self.group_node is None:
                        return mapping
                    scale_node, is_texture_tiling = utils.find_mapping_node(source, self.group_node)
                    if not scale_node: return mapping
                    if is_texture_tiling:
                        tiling_inputs = (
                            (AnimatedParameterType.TRANSLATION_X, 'Translate X'),
                            (AnimatedParameterType.TRANSLATION_Y, 'Translate Y'),
                            (AnimatedParameterType.SCALE_UNIFORM, 'Scale Multiplier'),
                            (AnimatedParameterType.SCALE_X, 'Scale X'),
                            (AnimatedParameterType.SCALE_Y, 'Scale Y'),
                        )
                        for animated_type, input_name in tiling_inputs:
                            input_socket = scale_node.inputs.get(input_name)
                            if input_socket is not None:
                                mapping[animated_type] = input_socket.default_value
                    elif scale_node.type == 'MAPPING':
                        mapping[AnimatedParameterType.SCALE_X] = scale_node.inputs['Scale'].default_value.x
                        mapping[AnimatedParameterType.SCALE_Y] = scale_node.inputs['Scale'].default_value.y
                        mapping[AnimatedParameterType.TRANSLATION_X] = scale_node.inputs['Location'].default_value.x
                        mapping[AnimatedParameterType.TRANSLATION_Y] = scale_node.inputs['Location'].default_value.y
            case 'real' | 'int' | 'bool':
                mapping[AnimatedParameterType.VALUE] = source
            case 'color':
                mapping[AnimatedParameterType.COLOR] = source
                
        return mapping

    def _animated_parameter_enum_value(self, block, parameter_type):
        if isinstance(parameter_type, AnimatedParameterType):
            return parameter_type.value
        if isinstance(parameter_type, int):
            return parameter_type
        return self._EnumIntValue(block, 'type', parameter_type)

    def _animated_parameter_value_is_default(self, parameter_type, value) -> bool:
        if parameter_type in {AnimatedParameterType.SCALE_UNIFORM, AnimatedParameterType.SCALE_X, AnimatedParameterType.SCALE_Y, self.scale_u, self.scale_v}:
            return value == 1
        if parameter_type in {AnimatedParameterType.TRANSLATION_X, AnimatedParameterType.TRANSLATION_Y, self.translation_u, self.translation_v}:
            return value == 0
        # Only identity texture transforms can omit their functions. Scalar
        # overrides still require a value function, including constants 0 and 1.
        return False

    def _set_animated_parameter_type(self, element, parameter_type):
        type_field = element.SelectField('type')
        if isinstance(parameter_type, AnimatedParameterType):
            type_field.Value = parameter_type.value
        elif isinstance(parameter_type, int):
            type_field.Value = parameter_type
        else:
            type_field.SetValue(parameter_type)
            
    def _setup_function_parameters(self, source: tuple[float] | bpy.types.Node,
                                   element: NativeTagStruct, parameter_type: str):
        block_animated_parameters = element.SelectField(self.function_parameters)
        mapping = self._function_parameters_from_node(source, parameter_type)
        for k, v in mapping.items():
            new = False
            enum_index = self._animated_parameter_enum_value(block_animated_parameters, k)
            if enum_index is None:
                sub_element = None
            else:
                sub_element = self._Element_from_field_value(block_animated_parameters, 'type', enum_index)
                if sub_element and self._animated_parameter_value_is_default(k, v):
                    block_animated_parameters.RemoveElement(sub_element.ElementIndex)
                    continue

            if sub_element is None:
                if self._animated_parameter_value_is_default(k, v): continue
                new = True
                sub_element = block_animated_parameters.AddElement()
                self._set_animated_parameter_type(sub_element, k)

            field_animation_function = sub_element.SelectField(self.animated_function)
            value = field_animation_function.Value
            if k in {'color', AnimatedParameterType.COLOR}:
                if new:
                    value.ColorGraphType = self._FunctionEditorColorGraphType(2) # Sets 2-color
                new_color = self._GameColor_from_RGB(*v)
                value.SetColor(0, new_color)
                value.SetColor(1, new_color)
            else:
                value.ClampRangeMin = v
            if new:
                value.MasterType = self._FunctionEditorMasterType(0) # basic type
                
        return mapping
    
    def _source_from_input_and_parameter_type(self, input, parameter_type, source_node=None):
        if source_node is None:
            source_node = self.group_node
        input_name = input.name.lower()
        match parameter_type:
            case 'bitmap':
                linked = utils.find_linked_node(source_node, input_name, 'TEX_IMAGE')
                if linked is None:
                    linked = utils.find_linked_node(source_node, input_name, 'TEX_ENVIRONMENT')
                return linked
            case 'real':
                return float(input.default_value)
            case 'int':
                return int(input.default_value)
            case 'bool':
                return int(bool(input.default_value))
            case 'color':
                return utils.get_material_albedo(source_node, input)
            
            
    # READING
    def to_nodes(self, blender_material, always_extract_bitmaps=False, generated_uvs=False):
        self.always_extract_bitmaps = always_extract_bitmaps
        self.game_functions = set()
        self.object_functions = set()
        self.sequence_drivers = {}
        self.has_rotating_bitmaps = False
        self.generated_uvs = generated_uvs
        if self.game == 'halo1':
            self._to_nodes_halo1(blender_material)
            self._import_classic_emission(blender_material)
            return
        if self.game == 'halo2':
            self._to_nodes_halo2(blender_material)
            self._import_classic_emission(blender_material)
            return
        self._get_info(self.reference_material_shader.Path if self.corinth else self.definition.Path)
        family = self.system_path.suffix.lstrip('.').casefold()
        has_group = self.group_supported and (
            self.game not in {'halo3', 'halo3odst'}
            or family in self.h3_group_families
        )
        if has_group:
            self._to_nodes_group(blender_material)
        else:
            self._to_nodes_bsdf(blender_material)
        
        if not self.corinth:
            flags = self._native_root.SelectField("Struct:render_method[0]/WordFlags:shader flags")
            if flags is not None and flags.TestBit("only render for shields"):
                utils.material_add_shield(blender_material)

    def _import_classic_emission(self, blender_material: bpy.types.Material):
        """Apply tag emission after building the classic shader's surface nodes."""
        if not utils.get_prefs().import_classic_shader_emission:
            return
        from .halo1_emissive import HALO1_EMISSIVE_SHADER_EXTENSIONS, read_material_emissive

        extensions = HALO1_EMISSIVE_SHADER_EXTENSIONS if self.game == 'halo1' else {'.shader'}
        if self.system_path.suffix.casefold() not in extensions:
            return
        power, color = read_material_emissive(self.system_path, self.tags_dir, self.game)
        prop = next((p for p in blender_material.nwo.material_props if p.type == 'emissive'), None)
        if prop is None:
            if power <= 0:
                return
            prop = blender_material.nwo.material_props.add()
            prop.type = 'emissive'
        prop.material_lighting_emissive_power = power
        prop.material_lighting_emissive_color = color
        utils.update_classic_emissive_material(blender_material, self.game)

    def _to_nodes_halo1_group(self, blender_material: bpy.types.Material, shader_type: str):
        """Populate the Halo 1 resource groups from their classic tag layouts."""
        group_tree = utils.add_node_from_resources('h1_nodes', f'foundry_h1.{shader_type}')
        if group_tree is None:
            utils.print_warning(f'Missing Halo 1 node group for {shader_type}; using basic material')
            return False

        blender_material.use_nodes = True
        tree = blender_material.node_tree
        nodes = tree.nodes
        nodes.clear()
        output = nodes.new('ShaderNodeOutputMaterial')
        output.location = (400, 0)
        group = nodes.new('ShaderNodeGroup')
        group.node_tree = group_tree
        group.location = (0, 0)
        tree.links.new(group.outputs['Shader'], output.inputs['Surface'])
        root = self.tag.root()

        def child(struct, name):
            return self.required_field(struct, name).as_struct()

        def copy_value(struct, field_name, socket_name=None):
            value = self.value(struct, field_name)
            if hasattr(value, 'red'):
                value = (value.red, value.green, value.blue, 1.0)
            group.inputs[socket_name or field_name.title()].default_value = value

        def enum_name(struct, name):
            return self.required_field(struct, name).options().current_name

        def copy_menu(struct, field_name, socket_name=None):
            # The resource menus use Guerilla's display spelling rather than
            # the normalized names in the native tag schemas.
            value = enum_name(struct, field_name)
            value = value.replace('double biased', 'double/biased')
            value = value.replace('self illumination', 'self-illumination')
            value = value.replace('change color', 'change-color')
            value = value.replace('auxiliary mask', 'multipurpose map alpha')
            group.inputs[socket_name or field_name.title()].default_value = value

        def scale(struct, name):
            return float(self.value(struct, name)) or 1.0

        texcoord = None

        def bitmap(struct, name, socket_name=None, *, non_color=False,
                   tiling=(1.0, 1.0), reflection=False):
            nonlocal texcoord
            reference = TagDocument.reference(self, struct, name)
            if reference is None or not reference.RelativePath:
                return None
            result = bitmap_to_image(reference.Filename, self.always_extract_bitmaps)
            if result.image is None:
                return None
            image_node = nodes.new('ShaderNodeTexEnvironment' if result.cubemap
                                   else 'ShaderNodeTexImage')
            image_node.location = (-400, -240 * sum(
                n.type in {'TEX_IMAGE', 'TEX_ENVIRONMENT'} for n in nodes))
            image_node.image = result.image
            if non_color:
                image_node.image.colorspace_settings.name = 'Non-Color'
            socket_name = socket_name or name.title()
            tree.links.new(image_node.outputs['Color'], group.inputs[socket_name])
            alpha_input = group.inputs.get(socket_name + ' Alpha')
            alpha_output = image_node.outputs.get('Alpha')
            if alpha_input is not None and alpha_output is not None:
                tree.links.new(alpha_output, alpha_input)

            if texcoord is None:
                texcoord = nodes.new('ShaderNodeTexCoord')
                texcoord.location = (-1000, 0)
            vector = texcoord.outputs['Reflection' if reflection else
                                      'Generated' if self.generated_uvs else 'UV']
            if not reflection and tiling != (1.0, 1.0):
                mapping = nodes.new('ShaderNodeMapping')
                mapping.location = (-700, image_node.location.y)
                mapping.inputs['Scale'].default_value = (*tiling, 1.0)
                tree.links.new(vector, mapping.inputs['Vector'])
                vector = mapping.outputs['Vector']
            tree.links.new(vector, image_node.inputs['Vector'])
            return image_node

        properties = child(root, 'properties')
        flags = self.required_field(properties, 'flags')
        illumination = child(root, 'self-illumination')
        reflection = child(root, 'reflection')
        blender_material.surface_render_method = 'DITHERED'

        if shader_type == 'shader_model':
            for flag, socket in (
                    ('detail after reflection', 'Detail After Reflections'),
                    ('two sided', 'Two-Sided'),
                    ('not alpha tested', 'Not Alpha-Tested'),
                    ('alpha blended decal', 'Alpha-Blended Decal'),
                    ('use xbox multipurpose channel order',
                     'Multipurpose Map Uses OG Xbox Channel Order')):
                group.inputs[socket].default_value = flags.get_flag(flag)
            if flags.get_flag('alpha blended decal'):
                blender_material.surface_render_method = 'BLENDED'

            change = child(root, 'change color')
            attribute_name = {'a': 'Primary Color', 'b': 'Secondary Color',
                              'c': 'Tertiary Color', 'd': 'Quaternary Color'}.get(
                                  enum_name(change, 'change color source'))
            if attribute_name is not None:
                attribute = nodes.new('ShaderNodeAttribute')
                attribute.attribute_type = 'INSTANCER'
                attribute.attribute_name = attribute_name
                attribute.location = (-400, 240)
                tree.links.new(attribute.outputs['Color'], group.inputs['Primary Change Color'])

            copy_value(illumination, 'animation color lower bound')
            copy_value(illumination, 'animation color upper bound')
            # Keep a static preview for classic animation functions, as before.
            group.inputs['Animation Color Bound Factor'].default_value = (
                0.0 if enum_name(illumination, 'animation function') == 'zero' else 1.0)
            maps = child(root, 'maps')
            uv_scale = (scale(maps, 'map u scale'), scale(maps, 'map v scale'))
            bitmap(maps, 'base map', tiling=uv_scale)
            bitmap(maps, 'multipurpose map', non_color=True, tiling=uv_scale)
            copy_menu(maps, 'detail function')
            copy_menu(maps, 'detail mask')
            detail_scale = scale(maps, 'detail map scale')
            detail_v_scale = float(self.value(maps, 'detail map v scale')) or detail_scale
            bitmap(maps, 'detail map', tiling=(uv_scale[0] * detail_scale,
                                              uv_scale[1] * detail_v_scale))
            specular = child(reflection, 'cube map properties')
            for field in ('perpendicular brightness', 'parallel brightness',
                          'perpendicular tint color', 'parallel tint color'):
                copy_value(specular, field)
            bitmap(reflection, 'cube map', 'Reflection Cube Map', reflection=True)
        else:
            group.inputs['Alpha Tested'].default_value = flags.get_flag('alpha tested')
            copy_menu(properties, 'shader environment type', 'Blend Type')
            diffuse = child(root, 'diffuse')
            bitmap(diffuse, 'base map')
            copy_menu(diffuse, 'detail map function')
            copy_menu(diffuse, 'micro detail map function')
            for name in ('primary detail map', 'secondary detail map', 'micro detail map'):
                detail_scale = scale(diffuse, name + ' scale')
                bitmap(diffuse, name, tiling=(detail_scale, detail_scale))

            bump = child(root, 'bump')
            bump_scale = scale(bump, 'bump map scale')
            bump_node = bitmap(bump, 'bump map', non_color=True,
                               tiling=(bump_scale, bump_scale))
            group.inputs['Bump Strength'].default_value = 1.0 if bump_node else 0.0
            for layer in ('primary', 'secondary', 'plasma'):
                copy_value(illumination, layer + ' on color')
                copy_value(illumination, layer + ' off color')
                group.inputs[layer.title() + ' Self-Illumination Activation Level'].default_value = (
                    0.0 if enum_name(illumination, layer + ' animation function') == 'zero' else 1.0)
            illumination_scale = scale(illumination, 'map scale')
            bitmap(illumination, 'map', 'Self-Illumination Map', non_color=True,
                   tiling=(illumination_scale, illumination_scale))
            specular = child(root, 'specular')
            for field in ('brightness', 'perpendicular color', 'parallel color'):
                copy_value(specular, field)
            for field in ('perpendicular brightness', 'parallel brightness'):
                copy_value(reflection, field)
            bitmap(reflection, 'reflection cube map', reflection=True)
        return True

    def _to_nodes_halo1(self, blender_material: bpy.types.Material):
        """Use Halo 1 resource groups, with basic materials for other families."""
        from .backend import TagDocument

        shader_type = self.system_path.suffix[1:].casefold()
        if shader_type in {'shader_model', 'shader_environment'}:
            if self._to_nodes_halo1_group(blender_material, shader_type):
                return

        blender_material.use_nodes = True
        tree = blender_material.node_tree
        nodes = tree.nodes
        nodes.clear()
        output = nodes.new(type='ShaderNodeOutputMaterial')
        output.location = (420, 0)
        bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
        bsdf.location = (120, 0)
        tree.links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

        root = self.tag.root()
        transparent = (shader_type.startswith('shader_transparent_')
                       or shader_type == 'decal')

        def child(struct, name: str):
            field = struct.field(name)
            return field.as_struct() if field is not None else None

        def enum_name(struct, name: str, default: str = '') -> str:
            field = None if struct is None else struct.field(name)
            options = None if field is None else field.options()
            if options is None or options.current_name is None:
                return default
            return options.current_name.casefold()

        alpha_tested = False
        if transparent:
            properties = child(root, 'properties')
            for field_name in ('flags', 'shader transparent glass flags'):
                flags = None if properties is None else properties.field(field_name)
                if flags is None:
                    continue
                try:
                    alpha_tested = flags.get_flag('alpha tested')
                except KeyError:
                    pass
                break
            blender_material.surface_render_method = ('DITHERED' if alpha_tested
                                                       else 'BLENDED')

        def bitmap(struct, name: str, *, non_color=False):
            if struct is None:
                return None
            reference = TagDocument.reference(self, struct, name)
            if reference is None or not reference.RelativePath:
                return None
            result = bitmap_to_image(reference.Filename, self.always_extract_bitmaps)
            node_type = ('ShaderNodeTexEnvironment' if getattr(result, 'cubemap', False)
                         else 'ShaderNodeTexImage')
            image_node = nodes.new(type=node_type)
            image_node.name = name
            image_node.label = name
            image_node.image = result.image
            if non_color and image_node.image is not None:
                image_node.image.colorspace_settings.name = 'Non-Color'
            return image_node

        base = bump = emission = detail = multipurpose = environment = None
        detail_layers = []
        material_color = None
        change_color_source = ''
        self_illumination = None
        reflection_properties = None
        reflection_color_properties = None
        reflection_brightness_scale = 1.0
        reflection_mask = None
        xbox_multipurpose_order = False
        if shader_type == 'shader_model':
            maps = child(root, 'maps')
            base = bitmap(maps, 'base map')
            detail = bitmap(maps, 'detail map')
            multipurpose = bitmap(maps, 'multipurpose map', non_color=True)
            change = child(root, 'change color')
            change_color_source = str(self.value(change, 'change color source')).casefold()
            self_illumination = child(root, 'self-illumination')
            reflection = child(root, 'reflection')
            reflection_properties = child(reflection, 'cube map properties')
            reflection_color_properties = reflection_properties
            environment = bitmap(reflection, 'cube map')
            properties = child(root, 'properties')
            flags = None if properties is None else properties.field('flags')
            if flags is not None:
                try:
                    xbox_multipurpose_order = flags.get_flag('use xbox multipurpose channel order')
                except KeyError:
                    pass
        elif shader_type == 'shader_environment':
            diffuse = child(root, 'diffuse')
            base = bitmap(diffuse, 'base map')
            detail_function = enum_name(diffuse, 'detail map function', 'double biased multiply')
            micro_function = enum_name(diffuse, 'micro detail map function', detail_function)
            for map_name, scale_name, function in (
                    ('primary detail map', 'primary detail map scale', detail_function),
                    ('secondary detail map', 'secondary detail map scale', detail_function),
                    ('micro detail map', 'micro detail map scale', micro_function)):
                detail_node = bitmap(diffuse, map_name)
                if detail_node is not None:
                    detail_layers.append((
                        detail_node, float(self.value(diffuse, scale_name)) or 1.0, function))
            if diffuse is not None and diffuse.field('material color') is not None:
                value = self.value(diffuse, 'material color')
                material_color = (value.red, value.green, value.blue, 1.0)
            bump = bitmap(child(root, 'bump'), 'bump map', non_color=True)
            emission = bitmap(child(root, 'self-illumination'), 'map')
            reflection_properties = child(root, 'reflection')
            reflection_color_properties = child(root, 'specular')
            environment = bitmap(reflection_properties, 'reflection cube map')
            if (reflection_color_properties is not None and
                    reflection_color_properties.field('brightness') is not None):
                reflection_brightness_scale = float(
                    self.value(reflection_color_properties, 'brightness'))
        elif shader_type == 'shader_transparent_glass':
            diffuse = child(root, 'diffuse')
            base = bitmap(diffuse, 'diffuse map')
            glass_detail = bitmap(diffuse, 'diffuse detail map')
            if glass_detail is not None:
                detail_layers.append((
                    glass_detail,
                    float(self.value(diffuse, 'diffuse detail map scale')) or 1.0,
                    'double biased multiply'))
            reflection = child(root, 'reflection')
            bump = bitmap(reflection, 'bump map', non_color=True)
            reflection_properties = child(reflection, 'reflection map properties')
            reflection_color_properties = reflection_properties
            environment = bitmap(reflection, 'reflection map')
        elif shader_type == 'shader_transparent_meter':
            base = bitmap(child(root, 'properties'), 'map')
        elif shader_type == 'shader_transparent_plasma':
            base = bitmap(child(root, 'primary noise map'), 'noise map')
        elif shader_type == 'shader_transparent_water':
            base = bitmap(child(root, 'properties'), 'base map')
        elif shader_type in {'shader_transparent_chicago', 'shader_transparent_generic'}:
            maps = self.block(root, 'maps')
            if len(maps):
                parameters = child(maps[0], 'parameters') or maps[0]
                base = bitmap(parameters, 'map')
        elif shader_type == 'shader_transparent_chicago_extended':
            maps = self.block(root, '4 stage maps')
            if not len(maps):
                maps = self.block(root, '2 stage maps')
            if len(maps):
                base = bitmap(child(maps[0], 'parameters'), 'map')
        elif shader_type == 'decal':
            appearance = child(root, 'appearance')
            shader = child(root, 'shader')
            base = bitmap(shader, 'map')
            if base is not None and self.generated_uvs:
                coordinates = nodes.new(type='ShaderNodeTexCoord')
                coordinates.location = (-760, 160)
                tree.links.new(coordinates.outputs['Generated'], base.inputs['Vector'])
            if appearance is not None:
                value = self.value(appearance, 'color upper bound')
                material_color = (value.red, value.green, value.blue, 1.0)

        if base is not None:
            base.location = (-520, 160)
            base_color = base.outputs['Color']
            if detail is not None:
                detail.location = (-520, -40)
                detail_scale = float(self.value(maps, 'detail map scale'))
                detail_v_scale = float(self.value(maps, 'detail map v scale'))
                if detail_scale:
                    texture = nodes.new(type='ShaderNodeTexCoord')
                    texture.location = (-1050, -40)
                    mapping = nodes.new(type='ShaderNodeMapping')
                    mapping.location = (-820, -40)
                    mapping.inputs['Scale'].default_value = (
                        detail_scale, detail_v_scale or detail_scale, 1.0)
                    tree.links.new(texture.outputs['UV'], mapping.inputs['Vector'])
                    tree.links.new(mapping.outputs['Vector'], detail.inputs['Vector'])
                multiply = nodes.new(type='ShaderNodeVectorMath')
                multiply.operation = 'MULTIPLY'
                multiply.location = (-250, 100)
                double = nodes.new(type='ShaderNodeVectorMath')
                double.operation = 'SCALE'
                double.inputs['Scale'].default_value = 2.0
                double.location = (-60, 100)
                tree.links.new(base.outputs['Color'], multiply.inputs[0])
                tree.links.new(detail.outputs['Color'], multiply.inputs[1])
                tree.links.new(multiply.outputs['Vector'], double.inputs['Vector'])
                base_color = double.outputs['Vector']

            for index, (detail_node, scale, function) in enumerate(detail_layers):
                detail_node.location = (-520, -40 - index * 180)
                if scale != 1.0:
                    texture = nodes.new(type='ShaderNodeTexCoord')
                    texture.location = (-1050, detail_node.location.y)
                    mapping = nodes.new(type='ShaderNodeMapping')
                    mapping.location = (-820, detail_node.location.y)
                    mapping.inputs['Scale'].default_value = (scale, scale, 1.0)
                    tree.links.new(texture.outputs['UV'], mapping.inputs['Vector'])
                    tree.links.new(mapping.outputs['Vector'], detail_node.inputs['Vector'])

                detail_color = detail_node.outputs['Color']
                if function == 'double biased add':
                    double_detail = nodes.new(type='ShaderNodeVectorMath')
                    double_detail.operation = 'SCALE'
                    double_detail.inputs['Scale'].default_value = 2.0
                    double_detail.location = (-250 + index * 180, -40)
                    subtract_one = nodes.new(type='ShaderNodeVectorMath')
                    subtract_one.operation = 'ADD'
                    subtract_one.inputs[1].default_value = (-1.0, -1.0, -1.0)
                    subtract_one.location = (-70 + index * 180, -40)
                    tree.links.new(detail_color, double_detail.inputs['Vector'])
                    tree.links.new(double_detail.outputs['Vector'], subtract_one.inputs[0])
                    combine = nodes.new(type='ShaderNodeVectorMath')
                    combine.operation = 'ADD'
                    tree.links.new(base_color, combine.inputs[0])
                    tree.links.new(subtract_one.outputs['Vector'], combine.inputs[1])
                else:
                    combine = nodes.new(type='ShaderNodeVectorMath')
                    combine.operation = 'MULTIPLY'
                    tree.links.new(base_color, combine.inputs[0])
                    tree.links.new(detail_color, combine.inputs[1])
                    if function == 'double biased multiply':
                        double_color = nodes.new(type='ShaderNodeVectorMath')
                        double_color.operation = 'SCALE'
                        double_color.inputs['Scale'].default_value = 2.0
                        double_color.location = (110 + index * 180, -40)
                        tree.links.new(combine.outputs['Vector'], double_color.inputs['Vector'])
                        base_color = double_color.outputs['Vector']
                        continue
                combine.location = (110 + index * 180, -40)
                base_color = combine.outputs['Vector']

            if material_color is not None:
                tint = nodes.new(type='ShaderNodeRGB')
                tint.outputs['Color'].default_value = material_color
                multiply_material = nodes.new(type='ShaderNodeVectorMath')
                multiply_material.operation = 'MULTIPLY'
                tree.links.new(base_color, multiply_material.inputs[0])
                tree.links.new(tint.outputs['Color'], multiply_material.inputs[1])
                base_color = multiply_material.outputs['Vector']

            if multipurpose is not None:
                multipurpose.location = (-520, -380)
                separate = nodes.new(type='ShaderNodeSeparateColor')
                separate.location = (-280, -380)
                tree.links.new(multipurpose.outputs['Color'], separate.inputs['Color'])

                attribute_names = {
                    'a': 'Primary Color',
                    'b': 'Secondary Color',
                    'c': 'Tertiary Color',
                    'd': 'Quaternary Color',
                }
                attribute_name = attribute_names.get(change_color_source)
                if attribute_name is not None:
                    attribute = nodes.new(type='ShaderNodeAttribute')
                    attribute.attribute_name = attribute_name
                    attribute.attribute_type = 'INSTANCER'
                    attribute.location = (-520, 420)
                    tinted = nodes.new(type='ShaderNodeVectorMath')
                    tinted.operation = 'MULTIPLY'
                    tinted.location = (-40, 320)
                    color_mix = nodes.new(type='ShaderNodeMixRGB')
                    color_mix.blend_type = 'MIX'
                    color_mix.location = (160, 260)
                    tree.links.new(base_color, tinted.inputs[0])
                    tree.links.new(attribute.outputs['Color'], tinted.inputs[1])
                    tree.links.new(base_color, color_mix.inputs[1])
                    tree.links.new(tinted.outputs['Vector'], color_mix.inputs[2])
                    change_mask = (separate.outputs['Blue'] if xbox_multipurpose_order
                                   else multipurpose.outputs['Alpha'])
                    tree.links.new(change_mask, color_mix.inputs[0])
                    base_color = color_mix.outputs['Color']

                specular_input = bsdf.inputs.get('Specular IOR Level')
                if specular_input is not None:
                    reflection_mask = (separate.outputs['Red'] if xbox_multipurpose_order
                                       else separate.outputs['Blue'])
                    tree.links.new(reflection_mask, specular_input)

                illumination_source = ('' if self_illumination is None else
                                       str(self.value(self_illumination, 'color source')).casefold())
                emission_input = bsdf.inputs.get('Emission Color')
                if emission_input is None:
                    emission_input = bsdf.inputs.get('Emission')
                emission_strength = bsdf.inputs.get('Emission Strength')
                if illumination_source != 'none' and emission_input is not None:
                    upper = self.value(self_illumination, 'animation color upper bound')
                    emission_color = nodes.new(type='ShaderNodeRGB')
                    emission_color.outputs['Color'].default_value = (
                        upper.red, upper.green, upper.blue, 1.0)
                    illuminated = nodes.new(type='ShaderNodeVectorMath')
                    illuminated.operation = 'MULTIPLY'
                    illuminated.location = (160, -220)
                    tree.links.new(base_color, illuminated.inputs[0])
                    tree.links.new(emission_color.outputs['Color'], illuminated.inputs[1])
                    tree.links.new(illuminated.outputs['Vector'], emission_input)
                    if emission_strength is not None:
                        tree.links.new(separate.outputs['Green'], emission_strength)

            if environment is not None:
                environment.location = (-520, 560)
                texture = nodes.new(type='ShaderNodeTexCoord')
                texture.location = (-1050, 560)
                tree.links.new(texture.outputs['Reflection'], environment.inputs['Vector'])

                perpendicular_brightness = 1.0
                parallel_brightness = 1.0
                perpendicular_tint = (1.0, 1.0, 1.0, 1.0)
                parallel_tint = perpendicular_tint
                if reflection_properties is not None:
                    if reflection_properties.field('perpendicular brightness') is not None:
                        perpendicular_brightness = float(
                            self.value(reflection_properties, 'perpendicular brightness'))
                    if reflection_properties.field('parallel brightness') is not None:
                        parallel_brightness = float(
                            self.value(reflection_properties, 'parallel brightness'))
                if reflection_color_properties is not None:
                    for field_name in ('perpendicular tint color', 'perpendicular color'):
                        if reflection_color_properties.field(field_name) is not None:
                            value = self.value(reflection_color_properties, field_name)
                            perpendicular_tint = (value.red, value.green, value.blue, 1.0)
                            break
                    for field_name in ('parallel tint color', 'parallel color'):
                        if reflection_color_properties.field(field_name) is not None:
                            value = self.value(reflection_color_properties, field_name)
                            parallel_tint = (value.red, value.green, value.blue, 1.0)
                            break
                perpendicular_brightness *= reflection_brightness_scale
                parallel_brightness *= reflection_brightness_scale

                facing = nodes.new(type='ShaderNodeLayerWeight')
                facing.location = (-280, 660)
                reflection_tint = nodes.new(type='ShaderNodeMixRGB')
                reflection_tint.blend_type = 'MIX'
                reflection_tint.location = (-40, 560)
                reflection_tint.inputs[1].default_value = tuple(
                    component * parallel_brightness for component in parallel_tint)
                reflection_tint.inputs[2].default_value = tuple(
                    component * perpendicular_brightness for component in perpendicular_tint)
                tree.links.new(facing.outputs['Facing'], reflection_tint.inputs[0])

                tinted_reflection = nodes.new(type='ShaderNodeVectorMath')
                tinted_reflection.operation = 'MULTIPLY'
                tinted_reflection.location = (170, 520)
                tree.links.new(environment.outputs['Color'], tinted_reflection.inputs[0])
                tree.links.new(reflection_tint.outputs['Color'], tinted_reflection.inputs[1])
                reflection_color = tinted_reflection.outputs['Vector']
                if reflection_mask is not None:
                    masked_reflection = nodes.new(type='ShaderNodeVectorMath')
                    masked_reflection.operation = 'SCALE'
                    masked_reflection.location = (370, 520)
                    tree.links.new(reflection_color, masked_reflection.inputs['Vector'])
                    tree.links.new(reflection_mask, masked_reflection.inputs['Scale'])
                    reflection_color = masked_reflection.outputs['Vector']

                add_reflection = nodes.new(type='ShaderNodeVectorMath')
                add_reflection.operation = 'ADD'
                add_reflection.location = (570, 360)
                tree.links.new(base_color, add_reflection.inputs[0])
                tree.links.new(reflection_color, add_reflection.inputs[1])
                base_color = add_reflection.outputs['Vector']
            tree.links.new(base_color, bsdf.inputs['Base Color'])
            if shader_type == 'decal':
                bounds = self.value(appearance, 'intensity')
                # Use the upper bound, like the preview tint. H1 treats 0..0 as 1..1.
                intensity = (1.0 if bounds.lower == bounds.upper == 0 else
                             max(0.0, min(1.0, float(bounds.upper))))
                self._halo1_decal_surface(
                    tree, output, bsdf, base, base_color,
                    enum_name(shader, 'framebuffer blend function', 'alpha blend'),
                    intensity)
                return
            elif transparent:
                alpha_output = base.outputs.get('Alpha')
                if alpha_output is not None:
                    tree.links.new(alpha_output, bsdf.inputs['Alpha'])
        if bump is not None:
            bump.location = (-520, -180)
            normal = nodes.new(type='ShaderNodeNormalMap')
            normal.location = (-180, -180)
            tree.links.new(bump.outputs['Color'], normal.inputs['Color'])
            tree.links.new(normal.outputs['Normal'], bsdf.inputs['Normal'])
        emission_input = bsdf.inputs.get('Emission Color')
        if emission_input is None:
            emission_input = bsdf.inputs.get('Emission')
        if emission is not None and emission_input is not None:
            emission.location = (-520, -500)
            tree.links.new(emission.outputs['Color'], emission_input)

    @staticmethod
    def _halo1_decal_surface(tree, output, bsdf, bitmap, color, blend, intensity):
        """Preview H1 framebuffer blends without turning neutral texels opaque.

        Coloured transparency implements destination * source in BLENDED Eevee
        materials and Cycles. Double multiply is limited by the transparent
        closure's energy range; subtract/min/max require framebuffer access.
        """
        nodes, links = tree.nodes, tree.links
        if blend in {'multiply', 'double multiply'}:
            if blend == 'double multiply':
                scale = nodes.new('ShaderNodeVectorMath')
                scale.operation = 'SCALE'
                scale.inputs['Scale'].default_value = 2.0
                scale.location = (-60, 220)
                links.new(color, scale.inputs['Vector'])
                color = scale.outputs['Vector']
                utils.print_warning('H1 double multiply decal preview cannot reproduce '
                                    'framebuffer brightening exactly')
            fade = nodes.new('ShaderNodeMixRGB')
            fade.label = 'Decal intensity (white is neutral)'
            fade.location = (140, 220)
            fade.inputs[0].default_value = intensity
            fade.inputs[1].default_value = (1.0, 1.0, 1.0, 1.0)
            links.new(color, fade.inputs[2])
            transparent = nodes.new('ShaderNodeBsdfTransparent')
            transparent.location = (360, 220)
            links.new(fade.outputs['Color'], transparent.inputs['Color'])
            links.new(transparent.outputs[0], output.inputs['Surface'])
            nodes.remove(bsdf)
        elif blend in {'add', 'alpha multiply add'}:
            emission = nodes.new('ShaderNodeEmission')
            emission.location = (140, 220)
            links.new(color, emission.inputs['Color'])
            emission.inputs['Strength'].default_value = intensity
            if blend == 'alpha multiply add':
                alpha = nodes.new('ShaderNodeMath')
                alpha.operation = 'MULTIPLY'
                alpha.inputs[1].default_value = intensity
                links.new(bitmap.outputs['Alpha'], alpha.inputs[0])
                links.new(alpha.outputs[0], emission.inputs['Strength'])
            transparent = nodes.new('ShaderNodeBsdfTransparent')
            transparent.location = (140, -40)
            add = nodes.new('ShaderNodeAddShader')
            add.location = (360, 100)
            links.new(transparent.outputs[0], add.inputs[0])
            links.new(emission.outputs[0], add.inputs[1])
            links.new(add.outputs[0], output.inputs['Surface'])
            nodes.remove(bsdf)
        else:
            if blend != 'alpha blend':
                utils.print_warning(f'H1 decal blend {blend!r} uses an alpha-blended '
                                    'preview; exact blending requires framebuffer access')
            alpha = nodes.new('ShaderNodeMath')
            alpha.operation = 'MULTIPLY'
            alpha.label = 'Decal alpha * intensity'
            alpha.location = (-100, -180)
            alpha.inputs[1].default_value = intensity
            links.new(bitmap.outputs['Alpha'], alpha.inputs[0])
            links.new(alpha.outputs[0], bsdf.inputs['Alpha'])
        output.location = (600, 100)

    def _to_nodes_halo2(self, blender_material: bpy.types.Material):
        """Populate the basic Halo 2 resource shader, with a Principled fallback."""
        from .backend import TagDocument

        blender_material.use_nodes = True
        tree = blender_material.node_tree
        nodes = tree.nodes
        nodes.clear()
        output = nodes.new(type='ShaderNodeOutputMaterial')
        output.location = (420, 0)
        bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
        bsdf.location = (120, 0)
        tree.links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

        root = self.tag.root()
        if self.system_path.suffix.casefold() == '.decal':
            blender_material.surface_render_method = 'BLENDED'
            reference = TagDocument.reference(self, root, 'bitmap')
            if reference is None or not reference.RelativePath:
                return
            result = bitmap_to_image(reference.Filename, self.always_extract_bitmaps)
            image_node = nodes.new(type='ShaderNodeTexImage')
            image_node.name = 'bitmap'
            image_node.label = 'bitmap'
            image_node.location = (-520, 160)
            image_node.image = result.image
            upper = self.value(root, 'color upper bounds')
            tint = nodes.new(type='ShaderNodeRGB')
            tint.outputs['Color'].default_value = (
                upper.red, upper.green, upper.blue, 1.0)
            tint.location = (-520, -40)
            multiply = nodes.new(type='ShaderNodeVectorMath')
            multiply.operation = 'MULTIPLY'
            multiply.location = (-180, 120)
            tree.links.new(image_node.outputs['Color'], multiply.inputs[0])
            tree.links.new(tint.outputs['Color'], multiply.inputs[1])
            tree.links.new(multiply.outputs['Vector'], bsdf.inputs['Base Color'])
            tree.links.new(image_node.outputs['Alpha'], bsdf.inputs['Alpha'])
            return

        group_tree = utils.add_node_from_resources('h2_nodes', 'Basic H2 shader')
        group = None
        if group_tree is not None:
            group = nodes.new('ShaderNodeGroup')
            group.node_tree = group_tree
            group.location = (120, 0)
            # A static import should not enable active camouflage by default.
            group.inputs['Active Camo amount'].default_value = 0.0

        template = TagDocument.reference(self, root, 'template')
        template_name = template.RelativePath.casefold() if template is not None else ''
        transparent = '\\transparent\\' in template_name
        if transparent:
            blender_material.surface_render_method = 'BLENDED'

        parameters = {}
        for element in self.block(root, 'parameters'):
            parameters[str(self.value(element, 'name')).casefold()] = element

        alpha_tested = ('alpha_test' in template_name or
                        'alphatest_map' in parameters)
        if alpha_tested:
            blender_material.surface_render_method = 'DITHERED'

        def color(name: str):
            element = parameters.get(name)
            if element is None:
                return None
            value = self.value(element, 'const color')
            return (value.red, value.green, value.blue, 1.0)

        def real(name: str, default: float = 0.0) -> float:
            element = parameters.get(name)
            return default if element is None else float(self.value(element, 'const value'))

        def image(name: str, *, non_color=False):
            element = parameters.get(name)
            if element is None:
                return None
            bitmap = TagDocument.reference(self, element, 'bitmap')
            if bitmap is None or not bitmap.RelativePath:
                return None
            result = bitmap_to_image(bitmap.Filename, self.always_extract_bitmaps)
            node_type = ('ShaderNodeTexEnvironment' if getattr(result, 'cubemap', False)
                         else 'ShaderNodeTexImage')
            image_node = nodes.new(type=node_type)
            image_node.name = name
            image_node.label = name
            image_node.image = result.image
            if non_color and image_node.image is not None:
                image_node.image.colorspace_settings.name = 'Non-Color'
            return image_node

        alpha_map = image('alpha_blend_map')
        alpha_test_map = image('alphatest_map', non_color=True)
        base = image('base_map')
        if base is None:
            base = alpha_map or image('self_illum_map')
        if base is not None:
            base.location = (-520, 160)
            base_color = base.outputs['Color']
            detail_nodes = [node for node in (image('detail_map'), image('secondary_detail_map'))
                            if node is not None]
            for index, detail in enumerate(detail_nodes):
                detail.location = (-520, -40 - index * 180)
                prefix = 'detail' if index == 0 else 'secondary_detail'
                scale_x = real(f'{prefix}_scale_x', 1.0) or 1.0
                scale_y = real(f'{prefix}_scale_y', scale_x) or scale_x
                if scale_x != 1.0 or scale_y != 1.0:
                    texture = nodes.new(type='ShaderNodeTexCoord')
                    texture.location = (-1050, detail.location.y)
                    mapping = nodes.new(type='ShaderNodeMapping')
                    mapping.location = (-820, detail.location.y)
                    mapping.inputs['Scale'].default_value = (scale_x, scale_y, 1.0)
                    tree.links.new(texture.outputs['UV'], mapping.inputs['Vector'])
                    tree.links.new(mapping.outputs['Vector'], detail.inputs['Vector'])
                if group is not None and index == 0:
                    tree.links.new(detail.outputs['Color'], group.inputs['detail_map'])
                    continue
                multiply = nodes.new(type='ShaderNodeVectorMath')
                multiply.operation = 'MULTIPLY'
                multiply.location = (-250 + index * 180, 160)
                double = nodes.new(type='ShaderNodeVectorMath')
                double.operation = 'SCALE'
                double.inputs['Scale'].default_value = 2.0
                double.location = (-70 + index * 180, 160)
                tree.links.new(base_color, multiply.inputs[0])
                tree.links.new(detail.outputs['Color'], multiply.inputs[1])
                tree.links.new(multiply.outputs['Vector'], double.inputs['Vector'])
                base_color = double.outputs['Vector']

            multiply_map = image('multiply_map')
            if multiply_map is not None:
                multiply_map.location = (-520, -400)
                multiply_color = nodes.new(type='ShaderNodeVectorMath')
                multiply_color.operation = 'MULTIPLY'
                multiply_color.location = (300, 160)
                tree.links.new(base_color, multiply_color.inputs[0])
                tree.links.new(multiply_map.outputs['Color'], multiply_color.inputs[1])
                base_color = multiply_color.outputs['Vector']

            change_map = image('change_color_map', non_color=True)
            if change_map is not None:
                change_map.location = (-520, -580)
                separate = nodes.new(type='ShaderNodeSeparateColor')
                separate.location = (-280, -580)
                tree.links.new(change_map.outputs['Color'], separate.inputs['Color'])
                masks = (
                    (separate.outputs['Red'], 'Primary Color'),
                    (separate.outputs['Green'], 'Secondary Color'),
                    (separate.outputs['Blue'], 'Tertiary Color'),
                    (change_map.outputs['Alpha'], 'Quaternary Color'),
                )
                for index, (mask, attribute_name) in enumerate(masks):
                    attribute = nodes.new(type='ShaderNodeAttribute')
                    attribute.attribute_name = attribute_name
                    attribute.attribute_type = 'INSTANCER'
                    attribute.location = (-40, -500 - index * 120)
                    tinted = nodes.new(type='ShaderNodeVectorMath')
                    tinted.operation = 'MULTIPLY'
                    tinted.location = (170, -420 - index * 120)
                    color_mix = nodes.new(type='ShaderNodeMixRGB')
                    color_mix.blend_type = 'MIX'
                    color_mix.location = (380, -340 - index * 120)
                    tree.links.new(base_color, tinted.inputs[0])
                    tree.links.new(attribute.outputs['Color'], tinted.inputs[1])
                    tree.links.new(mask, color_mix.inputs[0])
                    tree.links.new(base_color, color_mix.inputs[1])
                    tree.links.new(tinted.outputs['Vector'], color_mix.inputs[2])
                    base_color = color_mix.outputs['Color']

            if group is None:
                environment = image('environment_map')
                if environment is None:
                    environment = image('specular_cube_map')
                if environment is not None:
                    environment.location = (-520, 620)
                    texture = nodes.new(type='ShaderNodeTexCoord')
                    texture.location = (-1050, 620)
                    tree.links.new(texture.outputs['Reflection'], environment.inputs['Vector'])

                    environment_tint = color('env_tint_color') or color('environment_color')
                    glancing_tint = color('env_glancing_tint_color') or environment_tint
                    environment_tint = environment_tint or (1.0, 1.0, 1.0, 1.0)
                    glancing_tint = glancing_tint or environment_tint
                    environment_brightness = real('env_brightness', 1.0)
                    glancing_brightness = real('env_glancing_brightness', environment_brightness)

                    facing = nodes.new(type='ShaderNodeLayerWeight')
                    facing.location = (-280, 720)
                    reflection_tint = nodes.new(type='ShaderNodeMixRGB')
                    reflection_tint.blend_type = 'MIX'
                    reflection_tint.location = (-40, 620)
                    reflection_tint.inputs[1].default_value = tuple(
                        component * glancing_brightness for component in glancing_tint)
                    reflection_tint.inputs[2].default_value = tuple(
                        component * environment_brightness for component in environment_tint)
                    tree.links.new(facing.outputs['Facing'], reflection_tint.inputs[0])

                    tinted_reflection = nodes.new(type='ShaderNodeVectorMath')
                    tinted_reflection.operation = 'MULTIPLY'
                    tinted_reflection.location = (170, 580)
                    tree.links.new(environment.outputs['Color'], tinted_reflection.inputs[0])
                    tree.links.new(reflection_tint.outputs['Color'], tinted_reflection.inputs[1])
                    # A cubemap added directly to Base Color makes H2 surfaces look
                    # wet even when viewed head-on. Keep the tag's brightness and
                    # tint, but attenuate the reflection by the view angle.
                    fresnel_reflection = nodes.new(type='ShaderNodeVectorMath')
                    fresnel_reflection.operation = 'SCALE'
                    fresnel_reflection.location = (370, 580)
                    tree.links.new(tinted_reflection.outputs['Vector'], fresnel_reflection.inputs['Vector'])
                    tree.links.new(facing.outputs['Fresnel'], fresnel_reflection.inputs['Scale'])
                    add_reflection = nodes.new(type='ShaderNodeVectorMath')
                    add_reflection.operation = 'ADD'
                    add_reflection.location = (570, 360)
                    tree.links.new(base_color, add_reflection.inputs[0])
                    tree.links.new(fresnel_reflection.outputs['Vector'], add_reflection.inputs[1])
                    base_color = add_reflection.outputs['Vector']
            tree.links.new(base_color, bsdf.inputs['Base Color'])

        if transparent:
            alpha_source = alpha_map or base
            opacity = real('alpha_blend_opacity', 1.0)
            alpha_output = None if alpha_source is None else alpha_source.outputs.get('Alpha')
            if alpha_output is None:
                bsdf.inputs['Alpha'].default_value = opacity
            elif opacity == 1.0:
                tree.links.new(alpha_output, bsdf.inputs['Alpha'])
            else:
                multiply_alpha = nodes.new(type='ShaderNodeMath')
                multiply_alpha.operation = 'MULTIPLY'
                multiply_alpha.inputs[1].default_value = opacity
                multiply_alpha.location = (-100, -420)
                tree.links.new(alpha_output, multiply_alpha.inputs[0])
                tree.links.new(multiply_alpha.outputs[0], bsdf.inputs['Alpha'])
        elif alpha_test_map is not None:
            alpha_test_map.location = (-520, -760)
            alpha_output = alpha_test_map.outputs.get('Alpha')
            if alpha_output is not None:
                tree.links.new(alpha_output, bsdf.inputs['Alpha'])

        bump = image('bump_map', non_color=True)
        if bump is not None:
            bump.location = (-520, -180)
            normal = nodes.new(type='ShaderNodeNormalMap')
            normal.location = (-180, -180)
            tree.links.new(bump.outputs['Color'], normal.inputs['Color'])
            tree.links.new(normal.outputs['Normal'], bsdf.inputs['Normal'])

        specular = color('specular_color')
        specular_input = bsdf.inputs.get('Specular IOR Level')
        if specular is not None and specular_input is not None:
            specular_input.default_value = max(specular[:3])

        emission = image('self_illum_map')
        emission_input = bsdf.inputs.get('Emission Color')
        if emission_input is None:
            emission_input = bsdf.inputs.get('Emission')
        if emission is not None and emission_input is not None:
            emission.location = (-520, -500)
            emission_color = color('emissive_color') or color('self_illum_color')
            if emission_color is None:
                tree.links.new(emission.outputs['Color'], emission_input)
            else:
                tint = nodes.new(type='ShaderNodeRGB')
                tint.outputs['Color'].default_value = emission_color
                multiply_emission = nodes.new(type='ShaderNodeVectorMath')
                multiply_emission.operation = 'MULTIPLY'
                multiply_emission.location = (-100, -500)
                tree.links.new(emission.outputs['Color'], multiply_emission.inputs[0])
                tree.links.new(tint.outputs['Color'], multiply_emission.inputs[1])
                tree.links.new(multiply_emission.outputs['Vector'], emission_input)
            strength = bsdf.inputs.get('Emission Strength')
            if strength is not None:
                strength.default_value = max(float(self.value(parameters.get('emissive_power'), 'const value'))
                                             if parameters.get('emissive_power') is not None else 1.0, 1.0)
        elif (emission_color := color('self_illum_color') or color('emissive_color')) is not None and emission_input is not None:
            emission_input.default_value = emission_color

        if group is not None:
            base_input = bsdf.inputs['Base Color']
            if base_input.is_linked:
                tree.links.new(base_input.links[0].from_socket, group.inputs['base_map'])
            if bump is not None:
                tree.links.new(bump.outputs['Color'], group.inputs['bump_map'])
                nodes.remove(normal)
            camo = image('active_camo_bump_map', non_color=True)
            if camo is not None:
                camo.location = (-520, -1000)
                tree.links.new(camo.outputs['Color'], group.inputs['active_camo_bump_map'])
            environment = image('environment_map')
            if environment is None:
                environment = image('specular_cube_map')
            if environment is not None:
                environment.location = (-520, 620)
                texture = nodes.new('ShaderNodeTexCoord')
                texture.location = (-820, 620)
                tree.links.new(texture.outputs['Reflection'], environment.inputs['Vector'])
                tree.links.new(environment.outputs['Color'], group.inputs['environment_map'])
            group.inputs['env_tint_color'].default_value = (
                color('env_tint_color') or color('environment_color') or (1.0, 1.0, 1.0, 1.0))
            group.inputs['env_brightness'].default_value = real('env_brightness', 1.0)
            surface = group.outputs['Shader']
            if emission_input is not None and (emission_input.is_linked or
                    any(emission_input.default_value[:3])):
                emissive = nodes.new('ShaderNodeEmission')
                emissive.location = (350, -220)
                if emission_input.is_linked:
                    tree.links.new(emission_input.links[0].from_socket, emissive.inputs['Color'])
                else:
                    emissive.inputs['Color'].default_value = emission_input.default_value
                emissive.inputs['Strength'].default_value = bsdf.inputs['Emission Strength'].default_value
                add = nodes.new('ShaderNodeAddShader')
                add.location = (560, 0)
                tree.links.new(surface, add.inputs[0])
                tree.links.new(emissive.outputs[0], add.inputs[1])
                surface = add.outputs[0]
            if transparent or alpha_tested:
                alpha = bsdf.inputs['Alpha']
                transparent_node = nodes.new('ShaderNodeBsdfTransparent')
                mix = nodes.new('ShaderNodeMixShader')
                mix.location = (760, 0)
                if alpha.is_linked:
                    tree.links.new(alpha.links[0].from_socket, mix.inputs[0])
                else:
                    mix.inputs[0].default_value = alpha.default_value
                tree.links.new(transparent_node.outputs[0], mix.inputs[1])
                tree.links.new(surface, mix.inputs[2])
                surface = mix.outputs[0]
            tree.links.new(surface, output.inputs['Surface'])
            output.location = (1000, 0)
            nodes.remove(bsdf)

    def _option_value_from_index(self, index):
        if index >= self.block_options.Elements.Count:
            if self.reference.Path:
                with ShaderTag(path=self.reference.Path) as shader:
                    return shader._option_value_from_index(index)
            return 0
        option_enum = self.block_options.Elements[index].Fields[0].Data
        if option_enum == -1 and self.reference.Path:
            with ShaderTag(path=self.reference.Path) as shader:
                return shader._option_value_from_index(index)
        else:
            if option_enum == -1:
                return 0
            return option_enum
        
    # def _mapping_from_parameter_name(self, name, mapping={}):
    #     if type(name) == str:
    #         element = self._Element_from_field_value(self.block_parameters, 'parameter name', name)
    #     else:
    #         for n in name:
    #             element = self._Element_from_field_value(self.block_parameters, 'parameter name', n)
    #             if element: break
                
    #     if element is None:
    #         if not self.corinth and self.reference.Path:
    #             with ShaderTag(path=self.reference.Path) as shader:
    #                 shader._mapping_from_parameter_name(name, mapping)
    #         else:
    #             return
    #     else:
    #         block_animated_parameters = element.SelectField(self.function_parameters)
    #         for e in block_animated_parameters.Elements:
    #             ap_type = AnimatedParameterType(e.Fields[0].Value)
    #             ap = Function()
    #             ap.from_element(e, self.animated_function)
    #             mapping[ap_type] = ap
                    
    #         if not self.corinth and self.reference.Path:
    #             with ShaderTag(path=self.reference.Path) as shader:
    #                 shader._mapping_from_parameter_name(name, mapping)
                    
    def _image_from_parameter_name(self, name, blue_channel_fix=False):
        """Saves an image (or gets the already existing one) from a shader parameter element"""
        if type(name) == str:
            element = self._Element_from_field_value(self.block_parameters, 'parameter name', name)
        else:
            for n in name:
                 element = self._Element_from_field_value(self.block_parameters, 'parameter name', n)
                 if element: break
        if element is None:
            if not self.corinth and self.reference.Path:
                with ShaderTag(path=self.reference.Path) as shader:
                    shader.always_extract_bitmaps = self.always_extract_bitmaps
                    return shader._image_from_parameter_name(name)
            else:
                return
        bitmap_path = element.SelectField('bitmap').Path
        if not bitmap_path:
            return
        
        return bitmap_to_image(bitmap_path.Filename, self.always_extract_bitmaps).image
        
    def _mapping_from_parameter_name(self, name):
        if type(name) == str:
            element = self._Element_from_field_value(self.block_parameters, 'parameter name', name)
        else:
            for n in name:
                 element = self._Element_from_field_value(self.block_parameters, 'parameter name', n)
                 if element: break
        if element is None:
            if not self.corinth and self.reference.Path:
                with ShaderTag(path=self.reference.Path) as shader:
                    return shader._mapping_from_parameter_name(name)
            else:
                return
        
    def _color_from_parameter_name(self, name):
        color = [1, 1, 1, 1]
        if type(name) == str:
            element = self._Element_from_field_value(self.block_parameters, 'parameter name', name)
        else:
            for n in name:
                 element = self._Element_from_field_value(self.block_parameters, 'parameter name', n)
                 if element: break
        if element is None:
            if not self.corinth and self.reference.Path:
                with ShaderTag(path=self.reference.Path) as shader:
                    return shader._color_from_parameter_name(name)
            else:
                return
            
        block_animated_parameters = element.SelectField(self.function_parameters)
        color_element = self._Element_from_field_value(block_animated_parameters, 'type', 1)
        if color_element:
            game_color = color_element.SelectField(self.animated_function).Value.GetColor(0)
            if game_color.ColorMode == 1: # Is HSV
                game_color = game_color.ToRgb()
                
            color = [game_color.Red, game_color.Green, game_color.Blue, game_color.Alpha]
        
        return color
        
    def _image_from_parameter(self, parameter: OptionParameter, return_none_if_default=False):
        """Saves an image (or gets the already existing one) from a shader parameter element"""
        element = None
        bitmap_path = None
        wrap_mode = 'REPEAT'
        for element in self.block_parameters.Elements:
            if element.Fields[0].GetStringData() == parameter.name:
                break
        else:
            if not self.corinth and self.reference.Path:
                with ShaderTag(path=self.reference.Path) as shader:
                    shader.always_extract_bitmaps = self.always_extract_bitmaps
                    return shader._image_from_parameter(parameter)
            else:
                if return_none_if_default:
                    return
                else:
                    bitmap_path = parameter.default_bitmap
                    element = None
                    if bitmap_path is None:
                        return
        
        if bitmap_path is None:
            bitmap_path = element.SelectField('bitmap').Path

        if bitmap_path is None:
            if not self.corinth and self.reference.Path:
                with ShaderTag(path=self.reference.Path) as shader:
                    shader.always_extract_bitmaps = self.always_extract_bitmaps
                    result = shader._image_from_parameter(parameter)
                    if result is not None:
                        return result
                    
            if not return_none_if_default:
                bitmap_path = parameter.default_bitmap
                element = None
        elif element is not None and element.SelectField("bitmap flags").Data > 1:
            match element.SelectField("bitmap address mode x").Data:
                case 1 | 3: # clamp | black border
                    wrap_mode = 'CLIP'
                case 2 | 4 | 5: # Mirror
                    wrap_mode = 'MIRROR'
            match element.SelectField("bitmap address mode y").Data:
                case 1 | 3: # clamp | black border
                    wrap_mode = 'CLIP'
                case 2 | 4 | 5: # Mirror
                    wrap_mode = 'MIRROR'
            match element.SelectField("bitmap address mode").Data:
                case 1 | 3: # clamp | black border
                    wrap_mode = 'CLIP'
                case 2 | 4 | 5: # Mirror
                    wrap_mode = 'MIRROR'
                    
                
        if bitmap_path is None:
            return
        
        # EVIL exception for an EVIL cubemap
        if bitmap_path.RelativePathWithExtension == SK_TEST_CUBEMAP:
            return
            #bitmap_path = self._TagPath_from_string(DEFAULT_CUBEMAP)
        
        if not os.path.exists(bitmap_path.Filename):
            return
        
        info = bitmap_to_image(bitmap_path.Filename, self.always_extract_bitmaps)
                
        return info.image, wrap_mode, info.sequence_length
    
    def _normal_type_from_parameter_name(self, name):
        if not self.corinth:
            return NormalType.DIRECTX # Reach normals are always directx
        if type(name) == str:
            element = self._Element_from_field_value(self.block_parameters, 'parameter name', name)
        else:
            for n in name:
                 element = self._Element_from_field_value(self.block_parameters, 'parameter name', n)
                 if element: break
        if element is None:
            return NormalType.OPENGL
        bitmap_path = element.SelectField('bitmap').Path
        if bitmap_path:
            system_bitmap_path = Path(self.tags_dir, bitmap_path.RelativePathWithExtension)
            if not os.path.exists(system_bitmap_path):
                return NormalType.OPENGL
            try:
                with BitmapTag(path=bitmap_path) as bitmap:
                    return bitmap.normal_type()
            except:
                return NormalType.OPENGL
        else:
            return NormalType.OPENGL
                
    def _value_from_parameter(self, parameter: OptionParameter, value_type: AnimatedParameterType):
        default_value = parameter.default
        for element in self.block_parameters.Elements:
            if element.Fields[0].GetStringData() == parameter.name:
                match parameter.type:
                    case 2:
                        default_value = element.SelectField("real").Data
                    case 3:
                        default_value = element.SelectField(r"int\bool").Data
                    case 4:
                        default_value = bool(element.SelectField(r"int\bool").Data)
                break
        else:
            if not self.corinth and self.reference.Path:
                with ShaderTag(path=self.reference.Path) as shader:
                    return shader._value_from_parameter(parameter, value_type)
            else:
                return default_value
            
        for element in element.SelectField(self.function_parameters).Elements:
            if element.Fields[0].Value != value_type.value:
                continue
            func = Function()
            func.from_element(element, self.animated_function)
            return func

        if not self.corinth and self.reference.Path:
            with ShaderTag(path=self.reference.Path) as shader:
                return shader._value_from_parameter(parameter, value_type)
        else:
            return default_value
    
    def _set_alpha(self, alpha_type, blender_material):
        if alpha_type == 'blend':
            blender_material.surface_render_method = 'BLENDED'
        else:
            blender_material.surface_render_method = 'DITHERED'
            
    def _alpha_type(self, alpha_test, blend_mode):
        if blend_mode > 0:
            return 'blend'
        elif alpha_test > 0:
            return 'clip'
        else:
            return ''
    
    def _to_nodes_bsdf(self, blender_material: bpy.types.Material):
        tree = blender_material.node_tree
        nodes = tree.nodes
        # Clear it out
        nodes.clear()
        # Make the BSDF and Output
        output = nodes.new(type='ShaderNodeOutputMaterial')
        output.location = Vector((300, 0))
        bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
        tree.links.new(input=output.inputs[0], output=bsdf.outputs[0])
        albedo_enum = self._option_value_from_index(0)
        bump_mapping_enum = self._option_value_from_index(1)
        alpha_test_enum = self._option_value_from_index(2)
        specular_mask_enum = self._option_value_from_index(3)
        self_illumination_enum = self._option_value_from_index(6)
        blend_mode_enum = self._option_value_from_index(7)
        alpha_blend_source_enum = self._option_value_from_index(11)
        alpha_type = self._alpha_type(alpha_test_enum, blend_mode_enum)
        diffuse = None
        normal = None
        specular = None
        self_illum = None
        alpha = None
        if albedo_enum == 2:
            diffuse = BSDFParameter(tree, bsdf, bsdf.inputs[0], 'ShaderNodeRGB', data=self._color_from_parameter_name('albedo_color'))
        else:
            diffuse = BSDFParameter(tree, bsdf, bsdf.inputs[0], 'ShaderNodeTexImage', data=self._image_from_parameter_name('base_map'), mapping=self._mapping_from_parameter_name('base_map'), diffalpha=bool(alpha_type))
            if not diffuse.data:
                diffuse = BSDFParameter(tree, bsdf, bsdf.inputs[0], 'ShaderNodeRGB', data=self._color_from_parameter_name('albedo_color'))

        if bump_mapping_enum > 0:
            normal = BSDFParameter(tree, bsdf, bsdf.inputs['Normal'], 'ShaderNodeTexImage', data=self._image_from_parameter_name('bump_map', True), normal_type=self._normal_type_from_parameter_name('bump_map'), mapping=self._mapping_from_parameter_name('bump_map'))
            if not normal.data:
                normal = None
                
        if specular_mask_enum == 3:
            specular = BSDFParameter(tree, bsdf, bsdf.inputs['Specular IOR Level'], 'ShaderNodeTexImage', data=self._image_from_parameter_name('specular_mask_texture'), mapping=self._mapping_from_parameter_name('specular_mask_texture'))
            if not specular.data:
                specular = None
        elif specular_mask_enum > 0 and diffuse and type(diffuse.data) == bpy.types.Image:
            diffuse.diffspec = True
            
        if self_illumination_enum > 0:
            if self_illumination_enum == 4 and diffuse and type(diffuse.data) == bpy.types.Image:
                diffuse.diffillum = True
            else:
                self_illum = BSDFParameter(tree, bsdf, bsdf.inputs['Emission Color'], 'ShaderNodeTexImage', data=self._image_from_parameter_name(self.self_illum_map_names), mapping=self._mapping_from_parameter_name(self.self_illum_map_names))
            if self_illum and self_illum.data:
                bsdf.inputs['Emission Strength'].default_value = 1
                intensity_element = self._Element_from_field_value(self.block_parameters, 'parameter name', 'self_illum_intensity')
                if intensity_element:
                    value_element = self._Element_from_field_value(intensity_element.SelectField('animated parameters'), 'type', 0)
                    if value_element:
                        bsdf.inputs['Emission Strength'].default_value = value_element.SelectField(self.animated_function).Value.ClampRangeMin
            else:
                self_illum = None
                
        if alpha_type:
            if alpha_blend_source_enum > 1:
                alpha = BSDFParameter(tree, bsdf, bsdf.inputs['Alpha'], 'ShaderNodeTexImage', data=self._image_from_parameter_name('opacity_texture'), mapping=self._mapping_from_parameter_name('opacity_texture'))
            elif diffuse and diffuse.data and type(diffuse.data) == bpy.types.Image:
                diffuse.diffalpha = True
            
        if diffuse:
            diffuse.build(Vector((-300, 400)))
        if normal:
            normal.build(Vector((-200, 100)))
        if specular:
            specular.build(Vector((-300, -200)))
        if self_illum:
            self_illum.build(Vector((-300, -500)))
        if alpha:
            alpha.build(Vector((-600, 300)))
            
        self._set_alpha(alpha_type, blender_material)
        
        
    def get_diffuse_bitmap_data_for_granny(self) -> None | tuple:
        fill_alpha = True
        calc_blue = False
        # has_normal = self.block_options.Elements[1].Fields[0].Data > 0
        for element in self.block_parameters.Elements:
            match element.Fields[0].GetStringData():
                case "base_map":
                    fill_alpha = self.block_options.Elements[7].Fields[0].Data < 1
                # case "bump_map":
                #     if has_normal:
                #         calc_blue = True
                #     else: continue
                case _:
                    continue
                    
            p = element.SelectField("bitmap").Path
            if not p:
                continue
            full_path = p.Filename
            if not os.path.exists(full_path):
                continue
            
            bitmap_path = element.SelectField("bitmap").Path.RelativePathWithExtension
            with BitmapTag(path=bitmap_path) as bitmap:
                return bitmap.get_granny_data(fill_alpha, calc_blue)
            
    def _tiling_from_animated_parameters(self, tree: bpy.types.NodeTree, parameter: OptionParameter):
        animated_parameters = {}

        if not self.corinth and self.reference.Path:
            with ShaderTag(path=self.reference.Path) as shader:
                shader._recursive_tiling_parameters_get(parameter, animated_parameters)
                
        for element in self.block_parameters.Elements:
            if element.Fields[0].GetStringData() == parameter.name:
                for element in element.SelectField(self.function_parameters).Elements:
                    value_type = AnimatedParameterType(element.Fields[0].Value)
                    if value_type in {AnimatedParameterType.SCALE_UNIFORM, AnimatedParameterType.SCALE_X, AnimatedParameterType.SCALE_Y, AnimatedParameterType.TRANSLATION_X, AnimatedParameterType.TRANSLATION_Y}:
                        func = Function()
                        func.from_element(element, self.animated_function)
                        # if value_type == AnimatedParameterType.TRANSLATION_Y and ap.clamp_min != 0:
                        #     ap.clamp_min = -3.669 * ap.clamp_min -33.125
                        animated_parameters[value_type] = func
        
        if animated_parameters:
            node = tree.nodes.new('ShaderNodeGroup')
            if self.has_rotating_bitmaps:
                # SCALE X = the angle of rotation
                # TRANSLATION X, TRANSLATION Y = vector of the center of rotation
                node.node_tree = utils.add_node_from_resources("shared_nodes", 'Texture Rotate')
                for value_type, ap in animated_parameters.items():
                    if value_type not in {AnimatedParameterType.SCALE_X, AnimatedParameterType.TRANSLATION_X, AnimatedParameterType.TRANSLATION_Y}:
                        continue
                    self._setup_input_with_function(node.inputs[RotateNodeInputs[value_type.name].value], ap, uses_time=True)
            else:
                node.node_tree = utils.add_node_from_resources("shared_nodes", 'Texture Tiling')
                for value_type, ap in animated_parameters.items():
                    self._setup_input_with_function(node.inputs[TilingNodeInputs[value_type.name].value], ap, uses_time=True)
                    
            self.add_texcoord_node(tree, node.inputs[-1])
            return node
    
    def _recursive_tiling_parameters_get(self, parameter: OptionParameter, animated_parameters: dict):
        for element in self.block_parameters.Elements:
            if element.Fields[0].GetStringData() == parameter.name:
                for element in element.SelectField(self.function_parameters).Elements:
                    value_type = AnimatedParameterType(element.Fields[0].Value)
                    if value_type in {AnimatedParameterType.SCALE_UNIFORM, AnimatedParameterType.SCALE_X, AnimatedParameterType.SCALE_Y, AnimatedParameterType.TRANSLATION_X, AnimatedParameterType.TRANSLATION_Y}:
                        func = Function()
                        func.from_element(element, self.animated_function)
                        animated_parameters[value_type] = func
                    
        if not self.corinth and self.reference.Path:
            with ShaderTag(path=self.reference.Path) as shader:
                shader._recursive_tiling_parameters_get(parameter, animated_parameters)
            
    def group_set_image(self, tree: bpy.types.NodeTree, node: bpy.types.Node, parameter: OptionParameter, channel_type=ChannelType.DEFAULT, specified_input=None):
        result = self._image_from_parameter(parameter)
        if result is None:
            return
        
        data, wrap_mode, sequence_length = result
        
        if data is None:
            return
        
        is_equirectangular = "equirectangular" in data.name
        
        if is_equirectangular:
            data_node = tree.nodes.new('ShaderNodeTexEnvironment')
        else:
            data_node = tree.nodes.new('ShaderNodeTexImage')
            data_node.extension = wrap_mode
            
        data_node.image = data
        
        if sequence_length > 1:
            value = self._value_from_parameter(parameter, AnimatedParameterType.FRAME_INDEX)
            data_node.image_user.frame_duration = sequence_length
            data_node.image_user.frame_start = -sequence_length
            data_node.image_user.use_auto_refresh = True
            if isinstance(value, Function):
                text = value.input
                if text in ("one", "zero"):
                    text = "sequence_image"
                self.game_functions.add(text)
                result = tree.driver_add(f'nodes["{data_node.name}"].image_user.frame_offset')
                driver = result.driver
                driver.type = 'SCRIPTED'
                var = driver.variables.new()
                var.name = "var"
                var.type = 'SINGLE_PROP'
                var.targets[0].id = None
                var.targets[0].data_path = f'["{text}"]'
                driver.expression = f"{var.name} * {sequence_length} - {sequence_length - 0.9999}"
                self.sequence_drivers[(text, tree)] = (driver, sequence_length)
            else:
                result = tree.driver_add(f'nodes["{data_node.name}"].image_user.frame_offset')
                driver = result.driver
                driver.type = 'SCRIPTED'
                driver.expression = f"-{sequence_length - 1}"
        
        input_map = {i.name.lower(): i for i in node.inputs}
        
        if specified_input is None:
            match channel_type:
                case ChannelType.DEFAULT:
                    tree.links.new(input=input_map[parameter.ui_name], output=data_node.outputs[0])
                case ChannelType.RGB:
                    tree.links.new(input=input_map[f"{parameter.ui_name}.rgb"], output=data_node.outputs[0])
                case ChannelType.ALPHA:
                    tree.links.new(input=input_map[f"{parameter.ui_name}.a"], output=data_node.outputs[1])
                case ChannelType.RGB_ALPHA:
                    tree.links.new(input=input_map[f"{parameter.ui_name}.rgb"], output=data_node.outputs[0])
                    tree.links.new(input=input_map[f"{parameter.ui_name}.a"], output=data_node.outputs[1])
        else:
            match channel_type:
                case ChannelType.DEFAULT | ChannelType.RGB:
                    main_input = node.inputs[specified_input] if isinstance(specified_input, int) else input_map[specified_input]
                    tree.links.new(input=main_input, output=data_node.outputs[0])
                    alpha_input = node.inputs.get(f"{main_input.name}_alpha")
                    if alpha_input is not None:
                        if is_equirectangular:
                            data_node = tree.nodes.new('ShaderNodeTexImage')
                            data_node.image = data
                            
                        tree.links.new(input=alpha_input, output=data_node.outputs[1])
                            
                case ChannelType.ALPHA:
                    tree.links.new(input=node.inputs[specified_input] if isinstance(specified_input, int) else input_map[specified_input], output=data_node.outputs[1])
        
        tiling_node = self._tiling_from_animated_parameters(tree, parameter)
        if tiling_node is None:
            if self.generated_uvs:
                self.add_texcoord_node(tree, data_node.inputs[0])
        else:
            tree.links.new(input=data_node.inputs[0], output=tiling_node.outputs[0])
            
        return data_node
    
    def _add_group_node(self, tree: bpy.types.NodeTree, nodes: bpy.types.Nodes, name: str) -> bpy.types.Node:
        node = nodes.new(type='ShaderNodeGroup')
        if self.game in {'halo3', 'halo3odst'}:
            name = name.replace('foundry_reach.', 'foundry_h3.', 1)
            resource = 'h3_nodes'
        else:
            resource = 'reach_nodes'
        node.node_tree = utils.add_node_from_resources(resource, name)
        return node

    def _setup_palette_vector_node(self, tree: bpy.types.NodeTree, group_node: bpy.types.Node) -> bpy.types.Node | None:
        palette_vector_node = self._add_group_node(tree, tree.nodes, self.palette_vector_node_name)
        if palette_vector_node.node_tree is None:
            tree.nodes.remove(palette_vector_node)
            return None

        self.populate_chiefster_node(tree, palette_vector_node)

        palette_input = group_node.inputs.get("palette.rgb")
        if palette_input is None:
            palette_input = group_node.inputs.get("palette")
        if palette_input is None:
            return palette_vector_node

        palette_node = utils.find_linked_node(group_node, palette_input.name.lower(), "TEX_IMAGE")
        if palette_node is None:
            return palette_vector_node

        vector_input = palette_node.inputs.get("Vector")
        vector_output = palette_vector_node.outputs.get("Vector")
        if vector_input is not None and vector_output is not None:
            tree.links.new(input=vector_input, output=vector_output)

        return palette_vector_node
    
    def get_model_material_spec(self, node_material_model, uses_spec_exponent_min_max: bool):
        for element in self.block_parameters.Elements:
            if element.Fields[0].GetStringData() == "specular_color_by_angle":
                for animated_element in element.SelectField("animated parameters").Elements:
                    value = animated_element.SelectField(self.animated_function).Value
                    normal_color = value.GetColor(0)
                    if normal_color.ColorMode == 1:
                        normal_color = normal_color.ToRgb()
                    glancing_color = value.GetColor(1)
                    if glancing_color.ColorMode == 1:
                        glancing_color = glancing_color.ToRgb()
                        
                    node_material_model.inputs["glancing_specular_color"].default_value = glancing_color.Red, glancing_color.Green, glancing_color.Blue, 1
                    node_material_model.inputs["normal_specular_color"].default_value = normal_color.Red, normal_color.Green, normal_color.Blue, 1
                    node_material_model.inputs["specular_color_exponent"].default_value = value.GetExponent(0)
                    if uses_spec_exponent_min_max:
                        node_material_model.inputs["specular_color_exponent_min"].default_value = value.GetAmplitudeMin(0)
                        node_material_model.inputs["specular_color_exponent_max"].default_value = value.GetAmplitudeMax(0)
                    break
                else:
                    if self.reference.Path:
                        with ShaderTag(path=self.reference.Path) as shader:
                            shader.get_model_material_spec(node_material_model, uses_spec_exponent_min_max)
                break
        else:
            if self.reference.Path:
                with ShaderTag(path=self.reference.Path) as shader:
                    shader.get_model_material_spec(node_material_model, uses_spec_exponent_min_max)
    
    # def _add_group_material_model(self, tree: bpy.types.NodeTree, nodes: bpy.types.Nodes, name: str, supports_glancing_spec: bool, uses_spec_exponent_min_max: bool) -> bpy.types.Node:
    #     node_material_model = nodes.new(type="ShaderNodeGroup")
    #     node_material_model.node_tree = utils.add_node_from_resources("reach_nodes", f"material_model - {name}")
            
    #     self.populate_chiefster_node(tree, node_material_model)
        
    #     # specular color has be dealt with specially
    #     if supports_glancing_spec:
    #         self.get_model_material_spec(node_material_model, uses_spec_exponent_min_max)

    #     return node_material_model
    
    def add_texcoord_node(self, tree, input):
        nodes = tree.nodes
        node = nodes.new(type="ShaderNodeTexCoord" if self.generated_uvs else "ShaderNodeUVMap")
        if self.generated_uvs:
            vec_node = nodes.new(type="ShaderNodeVectorRotate")
            vec_node.rotation_type = 'Z_AXIS'
            vec_node.inputs[1].default_value = 0.5, 0.5, 0.5
            vec_node.inputs[3].default_value = radians(90)
            tree.links.new(input=vec_node.inputs[0], output=node.outputs[0])
            tree.links.new(input=input, output=vec_node.outputs[0])
        else:
            tree.links.new(input=input, output=node.outputs[0])

    def _misc_rotates_bitmaps(self):
        option = self._option_value_from_index(9)
        if self.game in {'halo3', 'halo3odst'}:
            return option == H3Misc.FIRST_PERSON_NEVER_W_ROTATING_BITMAPS.value
        return option == Misc.ROTATING_BITMAPS_SUPER_SLOW.value
    
    def _to_nodes_group(self, blender_material: bpy.types.Material):
        # Get options
        e_albedo = Albedo(self._option_value_from_index(0))
        e_bump_mapping = BumpMapping(self._option_value_from_index(1))
        e_alpha_test = AlphaTest(self._option_value_from_index(2))
        e_specular_mask = SpecularMask(self._option_value_from_index(3))
        material_model_enum = H3MaterialModel if self.game in {'halo3', 'halo3odst'} else MaterialModel
        e_material_model = material_model_enum(self._option_value_from_index(4))
        e_environment_mapping = EnvironmentMapping(self._option_value_from_index(5))
        e_self_illumination = SelfIllumination(self._option_value_from_index(6))
        e_blend_mode = BlendMode(self._option_value_from_index(7))
        e_alpha_blend_source = AlphaBlendSource(self._option_value_from_index(11))
        
        self.has_rotating_bitmaps = self._misc_rotates_bitmaps()

        if self.game in {'halo3', 'halo3odst'} and e_specular_mask == SpecularMask.SPECULAR_MASK_MULT_DIFFUSE:
            utils.print_warning('Unsupported H3/ODST specular mask: MULT_DIFFUSE. Using FROM_DIFFUSE instead')
            e_specular_mask = SpecularMask.SPECULAR_MASK_FROM_DIFFUSE
        
        if e_material_model.value > 4 and e_material_model not in {H3MaterialModel.GLASS, H3MaterialModel.SINGLE_LOBE_PHONG}:
            old_model = e_material_model.name
            e_material_model = material_model_enum.COOK_TORRANCE
            utils.print_warning(f"Unsupported material model : {old_model}. Using {e_material_model.name} instead")
            
        if e_bump_mapping.value > 4:
            old_bump = e_bump_mapping.name
            e_bump_mapping = BumpMapping.STANDARD
            utils.print_warning(f"Unsupported bump mapping : {old_bump}. Using {e_bump_mapping.name} instead")
            
        if e_environment_mapping.value > 2:
            old_env = e_environment_mapping.name
            e_environment_mapping = EnvironmentMapping.DYNAMIC
            utils.print_warning(f"Unsupported environment mapping : {old_env}. Using {e_environment_mapping.name} instead")
            
        # if e_blend_mode.value > BlendMode.DOUBLE_MULTIPLY.value:
        #     old_blend = e_blend_mode.name
        #     e_blend_mode = BlendMode.ALPHA_BLEND
        #     utils.print_warning(f"Unsupported blend mode : {old_blend}. Using {e_blend_mode.name} instead")
        
        self.shader_parameters = {}
        self.shader_parameters.update(self.category_parameters["albedo"][utils.game_str(e_albedo.name)])
        self.shader_parameters.update(self.category_parameters["bump_mapping"][utils.game_str(e_bump_mapping.name)])
        self.shader_parameters.update(self.category_parameters["alpha_test"][utils.game_str(e_alpha_test.name)])
        self.shader_parameters.update(self.category_parameters["specular_mask"].get(utils.game_str(e_specular_mask.name), {}))
        self.shader_parameters.update(self.category_parameters["material_model"][utils.game_str(e_material_model.name)])
        self.shader_parameters.update(self.category_parameters["environment_mapping"][utils.game_str(e_environment_mapping.name)])
        self_illumination_option = self._group_option_key('self_illumination', e_self_illumination)
        self.shader_parameters.update(self.category_parameters["self_illumination"][self_illumination_option])
        self.shader_parameters.update(self.category_parameters["blend_mode"][utils.game_str(e_blend_mode.name)])
        alpha_blend_source = self.category_parameters.get("alpha_blend_source")
        if alpha_blend_source is not None:
            self.shader_parameters.update(
                alpha_blend_source[utils.game_str(e_alpha_blend_source.name)])
        self.true_parameters = {option.ui_name: option for option in self.shader_parameters.values()}

        tree = blender_material.node_tree
        nodes = tree.nodes
        # Clear it out
        nodes.clear()
        
        illum_uses_diffuse = e_self_illumination in {SelfIllumination.FROM_DIFFUSE, SelfIllumination.SELF_ILLUM_TIMES_DIFFUSE}
        has_illum = e_self_illumination != SelfIllumination.OFF
        has_albedo = not (e_albedo == Albedo.CONSTANT_COLOR and has_illum and not illum_uses_diffuse)
        
        group_node = self._add_group_node(tree, nodes, f"foundry_reach.shader")
        
        group_node.inputs[0].default_value = e_albedo.name.lower().strip('_')
        group_node.inputs[1].default_value = e_bump_mapping.name.lower().strip('_')
        group_node.inputs[2].default_value = e_alpha_test.name.lower().strip('_')
        group_node.inputs[3].default_value = e_specular_mask.name.lower().strip('_')
        group_node.inputs[4].default_value = e_material_model.name.lower().strip('_')
        group_node.inputs[5].default_value = e_environment_mapping.name.lower().strip('_')
        group_node.inputs[6].default_value = self_illumination_option
        group_node.inputs[7].default_value = e_blend_mode.name.lower().strip('_')
        
        uses_palette_vector = (self.game not in {'halo3', 'halo3odst'}
                               and self._self_illumination_uses_palette_vector(e_self_illumination))
        excluded_parameters = self.palette_vector_parameters if uses_palette_vector else frozenset()
        self.populate_chiefster_node(tree, group_node, 8, excluded_parameters)
        if uses_palette_vector:
            self._setup_palette_vector_node(tree, group_node)
        
        if has_albedo and e_albedo in {Albedo.FOUR_CHANGE_COLOR, Albedo.FOUR_CHANGE_COLOR_APPLYING_TO_SPECULAR, Albedo.TWO_CHANGE_COLOR}:
            node_cc_primary = nodes.new(type="ShaderNodeAttribute")
            node_cc_primary.attribute_name = "Primary Color"
            node_cc_primary.attribute_type = 'INSTANCER'
            tree.links.new(input=group_node.inputs["Primary Color"], output=node_cc_primary.outputs[0])
            node_cc_secondary = nodes.new(type="ShaderNodeAttribute")
            node_cc_secondary.attribute_name = "Secondary Color"
            node_cc_secondary.attribute_type = 'INSTANCER'
            tree.links.new(input=group_node.inputs["Secondary Color"], output=node_cc_secondary.outputs[0])
            
            if e_albedo != Albedo.TWO_CHANGE_COLOR:
                node_cc_tertiary = nodes.new(type="ShaderNodeAttribute")
                node_cc_tertiary.attribute_name = "Tertiary Color"
                node_cc_tertiary.attribute_type = 'INSTANCER'
                tree.links.new(input=group_node.inputs["Tertiary Color"], output=node_cc_tertiary.outputs[0])
                node_cc_quaternary = nodes.new(type="ShaderNodeAttribute")
                node_cc_quaternary.attribute_name = "Quaternary Color"
                node_cc_quaternary.attribute_type = 'INSTANCER'
                tree.links.new(input=group_node.inputs["Quaternary Color"], output=node_cc_quaternary.outputs[0])
            
        if e_self_illumination in {SelfIllumination.CHANGE_COLOR, SelfIllumination.CHANGE_COLOR_DETAIL}:
            node_cc_primary = nodes.new(type="ShaderNodeAttribute")
            node_cc_primary.attribute_name = "Primary Color"
            node_cc_primary.attribute_type = 'INSTANCER'
            tree.links.new(input=group_node.inputs["Primary Color"], output=node_cc_primary.outputs[0])
            
        if e_blend_mode.value > 0 or e_alpha_test.value > 0:
            blender_material.surface_render_method = 'BLENDED'
            group_node.inputs["material is two-sided"].default_value = True
            
        if (self.game not in {'halo3', 'halo3odst'} and
                e_material_model in {MaterialModel.COOK_TORRANCE, MaterialModel.TWO_LOBE_PHONG, MaterialModel.ORGANISM}):
            self.get_model_material_spec(group_node, True)
        
        # Make the Output
        node_output = nodes.new(type='ShaderNodeOutputMaterial')

        # Link to output
        tree.links.new(input=node_output.inputs[0], output=group_node.outputs[0])
        
    def _setup_input_with_function(self, end_input, data: float | tuple | Function | int | bool, for_alpha=False, uses_time=False, color_no_alpha=False):
        tree: bpy.types.NodeTree = end_input.id_data
        if not isinstance(data, Function):
            if isinstance(data, tuple):
                if color_no_alpha:
                    end_input.default_value = data
                else:
                    if for_alpha:
                        end_input.default_value = data[1]
                    else:
                        end_input.default_value = data[0]
            elif isinstance(data, float) or isinstance(data, int) or isinstance(data, bool):
                match end_input.type:
                    case 'FLOAT' | 'ROTATION' | 'VALUE':
                        end_input.default_value = float(data)
                    case 'BOOLEAN':
                        end_input.default_value = bool(data)
                    case 'INT':
                        end_input.default_value = int(data)
                        
            return
        
        if data.master_type == FunctionEditorMasterType.Basic and not data.is_ranged:
            if data.color_type != FunctionEditorColorGraphType.Scalar and end_input.type == 'RGBA':
                end_input.default_value = data.colors[0]
            elif data.color_type == FunctionEditorColorGraphType.Scalar and end_input.type in {'VALUE', 'INT', 'BOOLEAN', 'ROTATION'}:
                if end_input.type == 'INT':
                    end_input.default_value = int(data.clamp_min)
                else:
                    end_input.default_value = data.clamp_min
            return
        
        tree.links.new(input=end_input, output=data.to_blend_nodes(tree, force_time_period=uses_time))
        if data.input.strip():
            if data.input_uses_group_node:
                self.object_functions.add(data.input)
            else:
                self.game_functions.add(data.input)
        if data.is_ranged and data.range.strip():
            if data.range_uses_group_node:
                self.object_functions.add(data.range)
            else:
                self.game_functions.add(data.range)
    
    def populate_chiefster_node(self, tree: bpy.types.NodeTree, node: bpy.types.Node, start_input=0, excluded_parameters=frozenset()):
        last_parameter_name = None
        last_input_node = None
        
        for input in node.inputs[start_input:]:
            
            if not input.is_icon_visible:
                continue
            
            parameter_name_ui = input.name.lower() if "." not in input.name else input.name.partition(".")[0].lower()
            if "gamma curve" in parameter_name_ui:
                # if any(srgb_name in parameter_name_ui for srgb_name in srgb_names):
                #     input.default_value = 2.2
                # else:
                #     input.default_value = 1
                # if last_input_node.image.colorspace_settings.name == 'Non-Color':
                #     input.default_value = 1
                # else:
                #     input.default_value = 1.95
                last_parameter_name = None
                continue
            input: bpy.types.NodeGroupInput
            if parameter_name_ui in excluded_parameters:
                last_parameter_name = None
                last_input_node = None
                continue
            if parameter_name_ui == last_parameter_name and last_input_node is not None:
                # plug in alpha
                alpha_input = node.inputs.get(f"{parameter_name_ui}.a")
                if alpha_input is None:
                    alpha_input = node.inputs.get(f"{parameter_name_ui}.a/specular_mask.a")
                    
                if alpha_input is not None:
                    if last_input_node.type == 'TEX_ENVIRONMENT':
                        data_node = tree.nodes.new('ShaderNodeTexImage')
                        data_node.image = last_input_node.image
                        last_input_node = data_node
                    tree.links.new(input=alpha_input, output=last_input_node.outputs[1])
            elif parameter_name_ui == f"{last_parameter_name}_alpha":
                self._setup_input_with_function(input, self._value_from_parameter(self.true_parameters.get(last_parameter_name), AnimatedParameterType.ALPHA), True)
            else:
                # parameter_type = self._parameter_type_from_name(parameter_name)
                parameter = self.true_parameters.get(parameter_name_ui)
                if parameter is None:
                    last_parameter_name = None
                    continue
                parameter_type = ParameterType(parameter.type)
                match parameter_type:
                    case ParameterType.COLOR | ParameterType.ARGB_COLOR:
                        self._setup_input_with_function(input, self._value_from_parameter(parameter, AnimatedParameterType.COLOR), color_no_alpha=parameter_type == ParameterType.COLOR)
                    case ParameterType.REAL | ParameterType.INT | ParameterType.BOOL:
                        self._setup_input_with_function(input, self._value_from_parameter(parameter, AnimatedParameterType.VALUE))
                    case _:
                        if ".rgb" in input.name:
                            last_input_node = self.group_set_image(tree, node, parameter, ChannelType.RGB, input.name.lower())
                        elif ".a" in input.name:
                            last_input_node = self.group_set_image(tree, node, parameter, ChannelType.ALPHA, input.name.lower())
                        else:
                            last_input_node = self.group_set_image(tree, node, parameter, ChannelType.DEFAULT, input.name.lower())
                        
                last_parameter_name = parameter_name_ui
                
    def _parameter_type_from_name(self, name: str):
        for element in self.block_parameters.Elements:
            if element.Fields[0].GetStringData() == name:
                return ParameterType(element.Fields[1].Value)
                
        return ParameterType.NONE
                

class BSDFParameter:
    """Representation of a Halo Shader parameter element in Blender node form"""
    
    def __init__(self, tree, main_node, input, link_node_type, data=None, default_value=None, mapping=[], normal_type: NormalType = None, diffalpha=False, diffillum=False, diffspec=False):
        self.tree = tree
        self.main_node = main_node
        self.input = input
        self.link_node_type = link_node_type
        self.data = data
        self.default_value = default_value
        self.mapping = mapping
        self.normal_type = normal_type
        self.diffalpha = diffalpha
        self.diffillum = diffillum
        self.diffspec = diffspec
        
    
    def build(self, vector=Vector((0, 0))):
        if not (self.data or self.default_value) or self.data == self.default_value:
            return
        
        output_index = 0
        data_node = self.tree.nodes.new(self.link_node_type)
        data_node.location = vector
        if self.link_node_type == 'ShaderNodeTexImage':
            data_node.image = self.data
        elif self.link_node_type == 'ShaderNodeRGB':
            data_node.outputs[0].default_value = self.data
        
        if self.normal_type is not None:
            normal_map_node = self.tree.nodes.new('ShaderNodeNormalMap')
            normal_map_node.location = vector
            self.tree.links.new(input=self.input, output=normal_map_node.outputs[0])
            if self.normal_type == NormalType.OPENGL:
                data_node.location.x = normal_map_node.location.x - 300
                data_node.location.y = normal_map_node.location.y
                self.tree.links.new(input=normal_map_node.inputs[1], output=data_node.outputs[0])
            else:
                combine_rgb = self.tree.nodes.new('ShaderNodeCombineColor')
                combine_rgb.location.x = normal_map_node.location.x - 200
                combine_rgb.location.y = normal_map_node.location.y
                self.tree.links.new(input=normal_map_node.inputs[1], output=combine_rgb.outputs[0])
                invert_color = self.tree.nodes.new('ShaderNodeInvert')
                invert_color.location.x = combine_rgb.location.x - 200
                invert_color.location.y = combine_rgb.location.y + 80
                self.tree.links.new(input=combine_rgb.inputs[1], output=invert_color.outputs[0])
                separate_rgb = self.tree.nodes.new('ShaderNodeSeparateColor')
                separate_rgb.location.x = invert_color.location.x - 200
                separate_rgb.location.y = combine_rgb.location.y
                self.tree.links.new(input=combine_rgb.inputs[0], output=separate_rgb.outputs[0])
                self.tree.links.new(input=invert_color.inputs[1], output=separate_rgb.outputs[1])
                self.tree.links.new(input=combine_rgb.inputs[2], output=separate_rgb.outputs[2])
                
                self.tree.links.new(input=separate_rgb.inputs[0], output=data_node.outputs[0])
                data_node.location.x = separate_rgb.location.x - 300
                data_node.location.y = separate_rgb.location.y
                
        elif self.link_node_type == 'ShaderNodeTexImage':
            self.tree.links.new(input=self.input, output=data_node.outputs[output_index])
            if self.diffspec:
                self.tree.links.new(input=self.main_node.inputs['Specular IOR Level'], output=data_node.outputs[1])
            if self.diffillum:
                self.tree.links.new(input=self.main_node.inputs['Emission Color'], output=data_node.outputs[1])
            if self.diffalpha:
                self.tree.links.new(input=self.main_node.inputs['Alpha'], output=data_node.outputs[1])
            
        if self.mapping:
            mapping_node = self.tree.nodes.new('ShaderNodeGroup')
            mapping_node.node_tree = utils.add_node_from_resources("shared_nodes", 'Texture Tiling')
            mapping_node.location.x = data_node.location.x - 300
            mapping_node.location.y = data_node.location.y
            try:
                scale_uni = self.mapping.get('scale_uni', 0)
                if scale_uni:
                    mapping_node.inputs[0].default_value = scale_uni
                scale_x = self.mapping.get('scale_x', 0)
                if scale_x:
                    mapping_node.inputs[1].default_value = scale_x
                scale_y = self.mapping.get('scale_y', 0)
                if scale_y:
                    mapping_node.inputs[2].default_value = scale_y
                    
                self.tree.links.new(input=data_node.inputs[0], output=mapping_node.outputs[0])
            except:
                pass
        
class ParameterType(Enum):
    NONE = -1
    BITMAP = 0
    COLOR = 1
    REAL = 2
    INT = 3
    BOOL = 4
    ARGB_COLOR = 5
        
        
