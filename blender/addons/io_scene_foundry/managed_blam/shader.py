

from enum import Enum
from math import radians
import multiprocessing
from pathlib import Path
import time
from mathutils import Vector

from .connected_material import Function, AnimatedParameterType, FunctionEditorColorGraphType, FunctionEditorMasterType, RotateNodeInputs, TilingNodeInputs

from .render_method_option import OptionParameter

from ..constants import NormalType
from ..managed_blam import Tag
from ..managed_blam.Tags import TagPath, TagsNameSpace
import os
from ..managed_blam.bitmap import BitmapTag, bitmap_to_image
from ..tools.export_bitmaps import export_bitmap
from .. import utils
import bpy

from ..managed_blam.render_method_definition import RenderMethodDefinitionTag

global_render_method_definition = None
last_group_node = None

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

def build_templates(shader_paths, do_print=False):
    new_template_count = 0
    processes = []
    max_process_count = multiprocessing.cpu_count()
    built_templates = set()
    per_template_timeout_seconds = 120
    
    if do_print: print("--- Validating templates for shaders")
    for spath in shader_paths:
        with ShaderTag(path=spath) as shader:
            template = shader.tag.SelectField("Struct:render_method[0]/Block:postprocess[0]/Reference:shader template")
            if template is None:
                continue
            template_path = shader.get_path_str(template.Path, True)
            if not template_path:
                continue
            
            path_template = Path(template_path)
            if not path_template.exists():
                definition = shader.definition
                definition_path = shader.get_path_str(definition.Path, True)
                if definition_path and Path(definition_path).exists():
                    template_name = path_template.with_suffix("").name
                    if template_name in built_templates:
                        continue
                    
                    built_templates.add(template_name)
                    
                    while len(processes) >= max_process_count:
                        processes = [p for p in processes if p.poll() is None]
                        time.sleep(0.1)
                    
                    if do_print: print(f"--- Building template {template_name} for {spath}")
                    new_template_count += 1
                    process = utils.run_tool(["generate-specified-template", "win", definition.Path.RelativePath, template_name], in_background=True, null_output=True)
                    processes.append((process, template_name))
                    
    if new_template_count == 0:
        return
    
    if do_print: print(f"--- Waiting for Tool processes to complete")
    for p, template_name in processes:
        start_wait = time.perf_counter()
        while p.poll() is None:
            if time.perf_counter() - start_wait > per_template_timeout_seconds:
                utils.print_warning(
                    f"Timed out building shader template '{template_name}' after {per_template_timeout_seconds}s. Continuing export."
                )
                try:
                    p.terminate()
                    time.sleep(0.2)
                    if p.poll() is None:
                        p.kill()
                except Exception:
                    pass
                break
            time.sleep(0.1)
                    
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

class ShaderTag(Tag):
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
    group_node_name = "foundry_reach.shader"
    group_option_start_input = 8
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
    
    def _read_fields(self):
        self.render_method = self.tag.SelectField("Struct:render_method").Elements[0]
        self.block_parameters = self.render_method.SelectField("parameters")
        self.block_options = self.render_method.SelectField('options')
        self.reference = self.render_method.SelectField('reference')
        if self.reference.Path and self.reference.Path == self.tag_path: # prevent recursion issues
            self.reference.Path = None
        self.definition = self.render_method.SelectField('definition')
        
    def get_global_material(self):
        global_material_field = self.tag.SelectField("StringId:material name")
        if global_material_field is None:
            global_material_field = self.tag.SelectField("StringId:material name 0")
            
        if global_material_field is None:
            return ""
            
        global_material = global_material_field.GetStringData()
        
        if not global_material and self.reference.Path is not None and self.path_exists(self.reference.Path):
            with ShaderTag(path=self.reference.Path) as ref_shader:
                return ref_shader.get_global_material()
        
        return global_material
    
    @classmethod
    def _get_info(cls, definition_path: TagPath):
        if cls.category_parameters is None:
            def_path = definition_path
            if def_path is None:
                cls.category_parameters = {}
                return
            with RenderMethodDefinitionTag(path=def_path) as render_method_definition:
                cls.category_parameters = render_method_definition.get_defaults()
                
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
        def _get_group_node(blender_material):
            """Gets a group node from a blender material node tree if one exists and it plugged into the output node"""
            tree = self.blender_material.node_tree
            if tree is None:
                return None
            nodes = tree.nodes
            for n in nodes:
                if n.type != "OUTPUT_MATERIAL":
                    continue
                links = n.inputs[0].links
                if not links:
                    continue
                from_node = links[0].from_node
                if from_node.type != "GROUP":
                    continue
                group_tree = from_node.node_tree
                if group_tree:
                    return from_node
            return None
        self.group_node = _get_group_node(blender_material)
        if self.corinth:
            self.custom = self.group_node is not None
        else:
            self.custom = self._group_node_matches(self.group_node)
        if linked_to_blender:
            self._edit_tag()
        elif self.corinth and self.material_shader:
            self.tag.SelectField("Reference:material shader").Path = self._TagPath_from_string(self.material_shader)
            
        return self.tag.Path.RelativePathWithExtension
        
    def _edit_tag(self):
        self.alpha_type = self._alpha_type_from_blender_material()
        used_group_export = bool(self.custom and self._from_nodes_group())
        if not used_group_export:
            self._build_basic(self._get_basic_mapping(self.blender_material))
        
        self.tag_has_changes = True

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
        if isinstance(expected, str):
            return group_name == expected
        return group_name in expected

    def _group_option_member_from_socket(self, category_name: str, enum_cls: type[Enum], socket_value):
        if socket_value is None:
            return None
        if isinstance(socket_value, str):
            wanted = utils.game_str(socket_value)
            for member in enum_cls:
                if utils.game_str(member.name) == wanted:
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
        return utils.game_str(enum_member.name)

    def _apply_group_options_from_node(self) -> dict[str, str]:
        selected = {}
        inputs = list(self.group_node.inputs)
        for category_name, enum_cls, option_index, socket_index in self.group_option_specs:
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

        if self.category_parameters is None:
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

        seen_parameters = set()
        inputs = list(self.group_node.inputs)
        for input_socket in inputs[self.group_option_start_input:]:
            input_base_name = input_socket.name.partition(".")[0]
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

            source = self._source_from_input_and_parameter_type(input_socket, source_type)
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
        alpha_blend_source = self.block_options.Elements[11].SelectField('short')
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
                if int(alpha_blend_source.GetStringData()) != 4:
                    alpha_blend_source.SetStringData('3') if map.get('alpha').inputs[0].links else alpha_blend_source.SetStringData('2')
                element = self._setup_parameter(map['alpha'], 'opacity_map', 'bitmap')
                if element:
                    self._setup_function_parameters(map['alpha'], element, 'bitmap')
        else:
            alpha_test.SetStringData('-1')
            blend_mode.SetStringData('-1')
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
                        factor = scale_node.inputs['Scale Multiplier'].default_value
                        mapping[self.scale_u] = scale_node.inputs['Scale X'].default_value * factor
                        mapping[self.scale_v] = scale_node.inputs['Scale Y'].default_value * factor
                    elif scale_node.type == 'MAPPING':
                        mapping[self.scale_u] = scale_node.inputs['Scale'].default_value.x
                        mapping[self.scale_v] = scale_node.inputs['Scale'].default_value.y
                        mapping[self.translation_u] = scale_node.inputs['Location'].default_value.x
                        mapping[self.translation_v] = scale_node.inputs['Location'].default_value.y
            case 'real' | 'int' | 'bool':
                mapping['value'] = source
            case 'color':
                mapping['color'] = source
                
        return mapping
            
    def _setup_function_parameters(self, source: tuple[float] | bpy.types.Node, element: TagsNameSpace.TagElement, parameter_type: str):
        block_animated_parameters = element.SelectField(self.function_parameters)
        mapping = self._function_parameters_from_node(source, parameter_type)
        for k, v in mapping.items():
            new = False
            enum_index = self._EnumIntValue(block_animated_parameters, 'type', k)
            if enum_index is None:
                sub_element = None
            else:
                sub_element = self._Element_from_field_value(block_animated_parameters, 'type', enum_index)
                if sub_element and (v == 1 or v == 0):
                    block_animated_parameters.RemoveElement(sub_element.ElementIndex)
                    continue

            if sub_element is None:
                if v == 1 or v == 0: continue
                new = True
                sub_element = block_animated_parameters.AddElement()
                sub_element.SelectField('type').SetValue(k)

            field_animation_function = sub_element.SelectField(self.animated_function)
            value = field_animation_function.Value
            if k == 'color':
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
    
    def _source_from_input_and_parameter_type(self, input, parameter_type):
        input_name = input.name.lower()
        match parameter_type:
            case 'bitmap':
                linked = utils.find_linked_node(self.group_node, input_name, 'TEX_IMAGE')
                if linked is None:
                    linked = utils.find_linked_node(self.group_node, input_name, 'TEX_ENVIRONMENT')
                return linked
            case 'real':
                return float(input.default_value)
            case 'int':
                return int(input.default_value)
            case 'bool':
                return int(bool(input.default_value))
            case 'color':
                return utils.get_material_albedo(self.group_node, input)
            
            
    # READING
    def to_nodes(self, blender_material, always_extract_bitmaps=False, generated_uvs=False):
        self.always_extract_bitmaps = always_extract_bitmaps
        self.game_functions = set()
        self.object_functions = set()
        self.sequence_drivers = {}
        self.has_rotating_bitmaps = False
        self.generated_uvs = generated_uvs
        self._get_info(self.reference_material_shader.Path if self.corinth else self.definition.Path)
        if self.group_supported:
            self._to_nodes_group(blender_material)
        else:
            self._to_nodes_bsdf(blender_material)
        
        if not self.corinth:
            flags = self.tag.SelectField("Struct:render_method[0]/WordFlags:shader flags")
            if flags is not None and flags.TestBit("only render for shields"):
                utils.material_add_shield(blender_material)
            
    def _option_value_from_index(self, index):
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
        node.node_tree = utils.add_node_from_resources("reach_nodes", name)
        return node
    
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
        node = nodes.new(type="ShaderNodeTexCoord")
        if self.generated_uvs:
            vec_node = nodes.new(type="ShaderNodeVectorRotate")
            vec_node.rotation_type = 'Z_AXIS'
            vec_node.inputs[1].default_value = 0.5, 0.5, 0.5
            vec_node.inputs[3].default_value = radians(90)
            tree.links.new(input=vec_node.inputs[0], output=node.outputs[0])
            tree.links.new(input=input, output=vec_node.outputs[0])
        else:
            tree.links.new(input=input, output=node.outputs[2])
    
    def _to_nodes_group(self, blender_material: bpy.types.Material):
        # Get options
        e_albedo = Albedo(self._option_value_from_index(0))
        e_bump_mapping = BumpMapping(self._option_value_from_index(1))
        e_alpha_test = AlphaTest(self._option_value_from_index(2))
        e_specular_mask = SpecularMask(self._option_value_from_index(3))
        e_material_model = MaterialModel(self._option_value_from_index(4))
        e_environment_mapping = EnvironmentMapping(self._option_value_from_index(5))
        e_self_illumination = SelfIllumination(self._option_value_from_index(6))
        e_blend_mode = BlendMode(self._option_value_from_index(7))
        e_parallax = Parallax(self._option_value_from_index(8))
        e_misc = Misc(self._option_value_from_index(9))
        e_wetness = Wetness(self._option_value_from_index(10))
        e_alpha_blend_source = AlphaBlendSource(self._option_value_from_index(11))
        
        self.has_rotating_bitmaps = e_misc == Misc.ROTATING_BITMAPS_SUPER_SLOW
        
        if e_material_model.value > 4:
            old_model = e_material_model.name
            e_material_model = MaterialModel.COOK_TORRANCE
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
        self.shader_parameters.update(self.category_parameters["specular_mask"][utils.game_str(e_specular_mask.name)])
        self.shader_parameters.update(self.category_parameters["material_model"][utils.game_str(e_material_model.name)])
        self.shader_parameters.update(self.category_parameters["environment_mapping"][utils.game_str(e_environment_mapping.name)])
        self.shader_parameters.update(self.category_parameters["self_illumination"][utils.game_str(e_self_illumination.name)])
        self.shader_parameters.update(self.category_parameters["blend_mode"][utils.game_str(e_blend_mode.name)])
        # self.shader_parameters.update(self.category_parameters[utils.game_str(e_parallax.name)])
        # self.shader_parameters.update(self.category_parameters[utils.game_str(e_misc.name)])
        # self.shader_parameters.update(self.category_parameters[utils.game_str(e_wetness.name)])
        self.shader_parameters.update(self.category_parameters["alpha_blend_source"][utils.game_str(e_alpha_blend_source.name)])
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
        group_node.inputs[6].default_value = e_self_illumination.name.lower().strip('_')
        group_node.inputs[7].default_value = e_blend_mode.name.lower().strip('_')
        
        self.populate_chiefster_node(tree, group_node, 8)
        
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
            
        if e_material_model in {MaterialModel.COOK_TORRANCE, MaterialModel.TWO_LOBE_PHONG, MaterialModel.ORGANISM}:
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
    
    def populate_chiefster_node(self, tree: bpy.types.NodeTree, node: bpy.types.Node, start_input=0):
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
                            last_input_node = self.group_set_image(tree, node, parameter, ChannelType.RGB)
                        elif ".a" in input.name:
                            last_input_node = self.group_set_image(tree, node, parameter, ChannelType.ALPHA)
                        else:
                            last_input_node = self.group_set_image(tree, node, parameter, ChannelType.DEFAULT)
                        
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
        
        
