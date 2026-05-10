import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
import time

import bpy

from .. import utils
from ..constants import MATERIAL_SHADERS_DIR
from ..managed_blam.material import MaterialTag
from ..managed_blam.material_shader import MaterialShaderTag
from ..managed_blam.render_method_definition import RenderMethodDefinitionTag
from ..managed_blam.shader import ShaderTag


SUPPORTED_SHADER_EXTS = {
    ".shader",
    ".shader_custom",
    ".shader_decal",
    ".shader_foliage",
    ".shader_fur",
    ".shader_fur_stencil",
    ".shader_glass",
    ".shader_halogram",
    ".shader_screen",
    ".shader_terrain",
    ".shader_water",
}

BITMAP_EXTERN_UNSUPPORTED = {
    "texture_camera",
    "texture_camera_z",
    "mirror",
    "refraction",
    "scope",
}

BITMAP_EXTERN_REMAP = {
    "nothing": "none",
    "none": "none",
    "screen_shader_display": "albedo_buffer",
    "screen_shader_normal": "normal_buffer",
}

BITMAP_PARAMETER_REMAP = {
    "base_map": "color_map",
    "bump_map": "normal_map",
    "normal_map": "normal_map",
    "detail_map": "color_detail_map",
    "bump_detail_map": "normal_detail_map",
    "specular_map": "specular_map",
    "specular_mask_texture": "specular_map",
    "self_illum_map": "selfillum_map",
    "environment_map": "reflection_map",
    "alpha_mask_map": "alpha_mask_map",
    "noise_map_a": "noise_a_map",
    "noise_map_b": "noise_b_map",
    "blend_map": "blend_map",
    "base_map_m_0": "layer2_comap",
    "base_map_m_1": "layer1_comap",
    "base_map_m_2": "layer0_comap",
    "bump_map_m_0": "layer2_nmmap",
    "bump_map_m_1": "layer1_nmmap",
    "bump_map_m_2": "layer0_nmmap",
    "detail_bump_m_0": "layer2_detailnmmap",
    "detail_bump_m_1": "layer1_detailnmmap",
    "detail_bump_m_2": "layer0_detailnmmap",
    "detail_map_m_0": "all_layers_color_detail_map", # pain, h4 has no per layer color detail
    "alpha_map": "alpha_map",
    "palette": "palette_map",
    "vector_map": "vector_map",
    "warp_map": "warp_map",
    "detail_map_a": "detail_map",
}

COLOR_PARAMETER_REMAP = {
    "albedo_color": ("albedo_tint", "diffuse_alpha", None),
    "specular_color_by_angle": ("specular_color", "glancing_specular_color", "fresnel_power"),
    "self_illum_color": ("si_color", None, None),
    "env_tint_color": ("reflection_color", "reflection_intensity", None),
    "color_wide": ("color_wide", "color_wide_alpha", None),
    "color_sharp": ("color_sharp", "color_sharp_alpha", None),
    "color_medium": ("color_medium", "color_medium_alpha", None),
    "tint_color": ("tint_color", "tint_color_alpha", None),
    "diffuse_coefficient_m_0": ("diffuse_coefficient_m_0", "r_color_tint", None),
    "diffuse_coefficient_m_1": ("diffuse_coefficient_m_1", "g_color_tint", None),
    "diffuse_coefficient_m_2": ("diffuse_coefficient_m_2", "b_color_tint", None),
    "add_color": ("add_color", "add_color_alpha", None),
}

REAL_PARAMETER_DIRECT = {
    "diffuse_contributuion": "diffuse_intensity",
    "diffuse_intensity": "diffuse_intensity",
    "area_specular_contribution": "specular_intensity",
    "specular_intensity": "specular_intensity",
    "self_illum_intensity": "si_intensity",
    "albedo_color_alpha": "diffuse_alpha",
    "environment_map_specular_contribution": "reflection_intensity",
    "animation_amplitude_horizontal": "animation_intensity",
    "foliage_translucency_scale": "translucent_intensity",
    "intensity": "tint_intensity",
    "vector_sharpness": "vector_sharpness",
    "antialias_tweak": "antialias_tweak",
    "warp_amount": "warp_amount",
    "detail_fade_a": "detail_fade",
    "palette_v": "palette_v",
    "detail_multiplier_a": "detail_multiplier",
    "fade": "fade",
}


@dataclass
class ShaderToMaterialReport:
    converted: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    unsupported: int = 0
    imported: int = 0
    dependencies_copied: int = 0
    deleted: int = 0
    warnings: list[str] = field(default_factory=list)
    converted_paths: dict[str, str] = field(default_factory=dict)


def _norm(value) -> str:
    return utils.game_str(str(value)).replace("-", "_")

def _tag_reference_path(tag: MaterialTag, relative_without_extension: str):
    relative = f"{relative_without_extension}.material_shader"
    return tag._TagPath_from_string(relative)

def _shader_name_for_log(path: str) -> str:
    return utils.dot_partition(path)


class ShaderToMaterialConverter:
    def __init__(self, delete_shaders: bool = False):
        self.definition_cache: dict[str, list[tuple[str, list[str]]]] = {}
        self.report = ShaderToMaterialReport()
        self.tags_path = Path(utils.get_tags_path())
        self.delete_shaders = delete_shaders
        self.imported_shader_paths: dict[str, str] = {}
        self.source_tag_roots: dict[str, Path] = {}
        self.material_output_paths: dict[str, str] = {}
        self.path_aliases: dict[str, str] = {}
        self.prepared_shader_paths: list[str] | None = None

    def prepare_shader_paths_for_gather(self, scope: str, path: str = ""):
        self.prepared_shader_paths = None

        match scope:
            case "BLEND":
                shader_paths: list[str] = []
                for mat in bpy.data.materials:
                    if not mat.nwo.RenderMaterial:
                        continue
                    source_path = mat.nwo.shader_path
                    if not source_path:
                        continue
                    shader_path = self._prepare_shader_source(source_path)
                    if shader_path:
                        shader_paths.append(shader_path)
                self.prepared_shader_paths = sorted(set(shader_paths), key=str.lower)
            case "PATH":
                if not path or len(path) < 3:
                    raise ValueError("No path supplied")
                full_path = self._full_path_from_input(path)
                if not full_path.exists():
                    raise FileNotFoundError("Path does not exist")
                if full_path.is_file():
                    shader_path = self._prepare_shader_source(path)
                    self.prepared_shader_paths = [shader_path] if shader_path else []
                else:
                    self.prepared_shader_paths = sorted(set(self._walk_shader_folder(full_path)), key=str.lower)

    def gather_shader_paths(self, scope: str, path: str = "") -> list[str]:
        if self.prepared_shader_paths is not None:
            return self.prepared_shader_paths

        shader_paths: list[str] = []

        match scope:
            case "BLEND":
                for mat in bpy.data.materials:
                    if not mat.nwo.RenderMaterial:
                        continue
                    source_path = mat.nwo.shader_path
                    if not source_path:
                        continue
                    full_path = self._full_path_from_input(source_path)
                    if full_path.exists() and full_path.suffix.lower() in SUPPORTED_SHADER_EXTS:
                        shader_paths.append(self._project_shader_path(full_path, source_path))
                    elif full_path.exists() and full_path.suffix.lower() in utils.shader_exts_reach:
                        self.report.unsupported += 1
                        self.report.warnings.append(f"Unsupported shader type skipped: {utils.relative_path(full_path)}")
            case "PATH":
                if not path or len(path) < 3:
                    raise ValueError("No path supplied")
                full_path = self._full_path_from_input(path)
                if not full_path.exists():
                    raise FileNotFoundError("Path does not exist")
                if full_path.is_file():
                    if full_path.suffix.lower() in SUPPORTED_SHADER_EXTS:
                        shader_paths.append(self._project_shader_path(full_path, path))
                    elif full_path.suffix.lower() in utils.shader_exts_reach:
                        self.report.unsupported += 1
                        self.report.warnings.append(f"Unsupported shader type skipped: {utils.relative_path(full_path)}")
                else:
                    shader_paths.extend(self._walk_shader_folder(full_path))
            case "ALL":
                shader_paths.extend(self._walk_shader_folder(self.tags_path))

        return sorted(set(shader_paths), key=str.lower)

    def _prepare_shader_source(self, source_path: str | Path) -> str:
        full_path = self._full_path_from_input(source_path)
        if full_path.exists() and full_path.suffix.lower() in SUPPORTED_SHADER_EXTS:
            return self._project_shader_path(full_path, source_path)
        if full_path.exists() and full_path.suffix.lower() in utils.shader_exts_reach:
            self.report.unsupported += 1
            self.report.warnings.append(f"Unsupported shader type skipped: {utils.relative_path(full_path)}")
        return ""

    def _walk_shader_folder(self, folder: Path) -> list[str]:
        shader_paths: list[str] = []
        for root, _, files in os.walk(folder):
            for file in files:
                suffix = Path(file).suffix.lower()
                full_path = Path(root, file)
                if suffix in SUPPORTED_SHADER_EXTS:
                    shader_paths.append(self._project_shader_path(full_path))
                elif suffix in utils.shader_exts_reach:
                    self.report.unsupported += 1
                    self.report.warnings.append(f"Unsupported shader type skipped: {utils.relative_path(full_path)}")
        return shader_paths

    def _full_path_from_input(self, path: str | Path) -> Path:
        input_path = Path(path)
        if input_path.is_absolute():
            return input_path

        relative = Path(utils.relative_path(input_path))
        current_project_path = Path(self.tags_path, relative)
        if current_project_path.exists():
            return current_project_path

        for tags_root in self._other_project_tag_roots():
            candidate = Path(tags_root, relative)
            if candidate.exists():
                print(f"--- Found missing project-relative shader in external project: {candidate}")
                return candidate

        return current_project_path

    def _other_project_tag_roots(self) -> list[Path]:
        tag_roots: list[Path] = []
        seen = {self._path_key(self.tags_path)}
        try:
            projects = utils.get_prefs().projects
        except Exception:
            projects = []

        for project in projects:
            tags_directory = project.tags_directory
            if not tags_directory:
                project_path = project.project_path
                tags_directory = str(Path(project_path, "tags")) if project_path else ""
            if not tags_directory:
                continue
            tags_root = Path(tags_directory)
            tags_key = self._path_key(tags_root)
            if tags_key in seen:
                continue
            if tags_root.exists():
                seen.add(tags_key)
                tag_roots.append(tags_root)

        try:
            current_project_path = Path(utils.get_project_path())
        except Exception:
            current_project_path = None

        if current_project_path and current_project_path.parent.exists():
            for sibling in current_project_path.parent.iterdir():
                tags_root = Path(sibling, "tags")
                tags_key = self._path_key(tags_root)
                if tags_key in seen:
                    continue
                if tags_root.exists():
                    seen.add(tags_key)
                    tag_roots.append(tags_root)
        return tag_roots

    def _path_key(self, path: str | Path) -> str:
        return str(path).replace("/", "\\").lower()

    def _is_in_tags_path(self, path: Path) -> bool:
        try:
            return path.is_relative_to(self.tags_path)
        except ValueError:
            return False

    def _project_shader_path(self, full_path: Path, source_path: str | Path | None = None) -> str:
        if self._is_in_tags_path(full_path):
            shader_path = utils.relative_path(full_path)
            if source_path is not None:
                self.path_aliases[self._path_key(source_path)] = shader_path
            return shader_path

        source_key = self._path_key(full_path.resolve())
        existing_shader_path = self.imported_shader_paths.get(source_key)
        if existing_shader_path:
            if source_path is not None:
                self.path_aliases[self._path_key(source_path)] = existing_shader_path
            return existing_shader_path

        with utils.TagImportMover(self.tags_path, full_path) as mover:
            shader_path = mover.tag_path
            if mover.needs_to_move:
                self.report.imported += 1
                self.source_tag_roots[self._path_key(shader_path)] = mover.potential_source_tag_dir
                original_shader_path = self._original_relative_shader_path(full_path, source_path, mover.potential_source_tag_dir)
                self.material_output_paths[self._path_key(shader_path)] = str(Path(original_shader_path).with_suffix(".material"))
                print(f"--- Copied external shader into current project: {shader_path}")

        self.imported_shader_paths[source_key] = shader_path
        self.path_aliases[self._path_key(full_path)] = shader_path
        self.path_aliases[self._path_key(utils.relative_path(full_path))] = shader_path
        if source_path is not None:
            self.path_aliases[self._path_key(source_path)] = shader_path
        return shader_path

    def _original_relative_shader_path(
        self,
        full_path: Path,
        source_path: str | Path | None = None,
        source_tag_root: Path | None = None,
    ) -> str:
        if source_path is not None:
            source_path = Path(source_path)
            if not source_path.is_absolute():
                return str(Path(utils.relative_path(source_path)))

        if source_tag_root is not None:
            try:
                return str(full_path.relative_to(source_tag_root))
            except ValueError:
                pass

        return utils.relative_path(full_path)

    def _material_path_for_shader(self, shader_path: str) -> str:
        return self.material_output_paths.get(self._path_key(shader_path), str(Path(shader_path).with_suffix(".material")))

    def convert_paths(self, shader_paths: list[str], update_blend_references: bool = False) -> ShaderToMaterialReport:
        successful_shader_paths: list[str] = []
        for shader_path in shader_paths:
            material_path = self.convert_shader(shader_path)
            if material_path:
                self._record_converted_path(shader_path, material_path)
                successful_shader_paths.append(shader_path)

        if update_blend_references and self.report.converted_paths:
            for mat in bpy.data.materials:
                shader_path = utils.relative_path(mat.nwo.shader_path)
                material_path = self.report.converted_paths.get(self._path_key(shader_path))
                if material_path:
                    mat.nwo.shader_path = material_path

        if self.delete_shaders and successful_shader_paths:
            self._delete_converted_shaders(successful_shader_paths)

        return self.report

    def _record_converted_path(self, shader_path: str, material_path: str):
        shader_key = self._path_key(shader_path)
        self.report.converted_paths[shader_key] = material_path
        for source_key, imported_shader_path in self.path_aliases.items():
            if self._path_key(imported_shader_path) == shader_key:
                self.report.converted_paths[source_key] = material_path

    def _delete_converted_shaders(self, shader_paths: list[str]):
        for shader_path in sorted(set(shader_paths), key=str.lower):
            full_path = self._full_path_from_input(shader_path)
            if full_path.suffix.lower() not in SUPPORTED_SHADER_EXTS:
                continue
            if not self._is_in_tags_path(full_path):
                warning = f"Refusing to delete shader outside current project: {shader_path}"
                self.report.warnings.append(warning)
                print(f"*** {warning}")
                continue
            if not full_path.exists():
                continue
            try:
                full_path.unlink()
            except OSError as exc:
                warning = f"Failed to delete shader {shader_path}: {exc}"
                self.report.warnings.append(warning)
                print(f"*** {warning}")
                continue
            self.report.deleted += 1
            print(f"    Deleted source shader {utils.relative_path(full_path)}")

    def convert_shader(self, shader_path: str) -> str:
        if Path(shader_path).suffix.lower() not in SUPPORTED_SHADER_EXTS:
            self.report.unsupported += 1
            print(f"--- Skipping unsupported shader type: {shader_path}")
            return ""

        material_path = self._material_path_for_shader(shader_path)
        Path(self.tags_path, material_path).parent.mkdir(parents=True, exist_ok=True)
        print(f"--- Converting {_shader_name_for_log(shader_path)}")

        with ShaderTag(path=shader_path) as shader:
            self._copy_external_shader_dependencies(shader_path, shader)
            with MaterialTag(path=material_path) as material:
                material_was_new = material.tag_is_new
                if not material_was_new and not self._material_is_converted_from_shader(material):
                    self.report.skipped += 1
                    print(f"    Skipped existing non-converted material: {material_path}")
                    return material_path

                self._mark_material_converted(material)
                success = self._convert_render_method_to_material(material, shader, Path(shader_path).suffix.lower())
                self._fix_materials(material)
                material.tag_has_changes = True

                if success:
                    if material_was_new:
                        self.report.converted += 1
                    else:
                        self.report.updated += 1
                    print(f"    Wrote {material_path}")
                    return material_path
                else:
                    self.report.failed += 1
                    self.report.warnings.append(f"{shader_path}: converted with unsupported or defaulted features")
                    print(f"    Converted with warnings: {material_path}")
                    return ""

        return ""

    def _copy_external_shader_dependencies(self, shader_path: str, shader: ShaderTag):
        source_tag_root = self.source_tag_roots.get(self._path_key(shader_path))
        if not source_tag_root:
            return

        if not source_tag_root.exists():
            warning = f"Cannot copy dependencies for {shader_path}; source tags folder not found: {source_tag_root}"
            self.report.warnings.append(warning)
            print(f"*** {warning}")
            return

        self._copy_loaded_shader_dependencies(shader, source_tag_root, set())

    def _copy_loaded_shader_dependencies(self, shader: ShaderTag, source_tag_root: Path, seen_shader_refs: set[str]):
        if shader.definition is not None:
            self._copy_tagpath_dependency(shader.definition.Path, source_tag_root, "render method definition")

        for bitmap_path in self._bitmap_references_from_shader(shader):
            self._copy_tagpath_dependency(bitmap_path, source_tag_root, "bitmap")

        if shader.reference is None:
            return

        reference_path = shader.reference.Path
        if reference_path is None:
            return

        reference_key = self._path_key(reference_path.RelativePathWithExtension)
        if reference_key in seen_shader_refs:
            return

        self._copy_tagpath_dependency(reference_path, source_tag_root, "referenced shader")
        if not self._tagpath_exists_in_current_project(reference_path):
            return

        seen_shader_refs.add(reference_key)
        with ShaderTag(path=reference_path) as reference_shader:
            self._copy_loaded_shader_dependencies(reference_shader, source_tag_root, seen_shader_refs)

    def _bitmap_references_from_shader(self, shader: ShaderTag):
        for shader_parameter in shader.block_parameters.Elements:
            parameter_type = int(shader_parameter.Fields[1].Value)
            if parameter_type != 0:
                continue
            bitmap_path = shader_parameter.SelectField("Reference:bitmap").Path
            if bitmap_path is not None:
                yield bitmap_path

    def _tagpath_exists_in_current_project(self, tag_path) -> bool:
        if tag_path is None:
            return False
        return Path(self.tags_path, tag_path.RelativePathWithExtension).exists()

    def _copy_tagpath_dependency(self, tag_path, source_tag_root: Path, dependency_type: str) -> bool:
        if tag_path is None:
            return False

        relative = tag_path.RelativePathWithExtension
        destination = Path(self.tags_path, relative)
        if destination.exists():
            return True

        source = Path(source_tag_root, relative)
        if not source.exists():
            warning = f"Missing external {dependency_type} dependency: {relative}"
            self.report.warnings.append(warning)
            print(f"*** {warning}")
            return False

        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        self.report.dependencies_copied += 1
        print(f"    Copied external {dependency_type}: {relative}")
        return True

    def _material_is_converted_from_shader(self, material: MaterialTag) -> bool:
        return material.tag.SelectField("flags").TestBit("converted from shader")

    def _mark_material_converted(self, material: MaterialTag):
        material.tag.SelectField("flags").SetBit("converted from shader", True)

    def _convert_render_method_to_material(self, material: MaterialTag, shader: ShaderTag, shader_group: str) -> bool:
        success = True
        self._clear_block(material.tag, "Block:postprocess definition")
        material.block_parameters.RemoveAllElements()

        success &= self._set_material_shader_from_shader(material, shader, shader_group)
        self._set_material_physics_from_shader(material, shader, shader_group)
        self._set_blend_mode(material, shader, shader_group)
        success &= self._set_material_shader_parameters_from_shader(material, shader)
        self._set_material_shader_parameter_defaults(material, shader)
        self._set_material_flags(material, shader, shader_group)
        self._set_additional_material_properties(material, shader, shader_group)
        return success

    def _clear_block(self, container, field_name: str):
        container.SelectField(field_name).RemoveAllElements()

    def _material_shader_path(self, *parts: str) -> str:
        return str(Path(MATERIAL_SHADERS_DIR, *parts)).replace("/", "\\")

    def _set_material_shader_reference(self, material: MaterialTag, relative_without_extension: str):
        material.reference_material_shader.Path = _tag_reference_path(material, relative_without_extension)

    def _set_material_shader_from_decal_shader(self, material: MaterialTag, shader: ShaderTag) -> bool:
        result = True
        selected_albedo = self._selected_option(shader, "albedo")
        selected_bump = self._selected_option(shader, "bump_mapping")
        selected_tinting = self._selected_option(shader, "tinting")

        target = self._material_shader_path("decals", "base")
        if not selected_albedo.startswith("diffuse_") and selected_albedo != "change_color":
            if selected_albedo == "palettized":
                target = self._material_shader_path("decals", "palette")
            elif selected_albedo == "palettized_plus_alpha":
                target = self._material_shader_path("decals", "palette_alpha")
            elif selected_albedo == "vector_alpha":
                target = self._material_shader_path("decals", "vector_alpha")
            else:
                result = False
        elif selected_albedo.startswith("diffuse_") and selected_bump != "leave":
            target = self._material_shader_path("decals", "normal")
        elif selected_tinting == "none":
            target = self._material_shader_path("decals", "base")
        else:
            unmodulated = selected_tinting == "unmodulated"
            if not unmodulated and selected_tinting == "partially_modulated":
                intensity = self._parameter_by_name(shader, "intensity", 2)
                modulation_factor = self._parameter_by_name(shader, "modulation_factor", 2)
                if intensity is not None and modulation_factor is not None:
                    unmodulated = (
                        abs(self._evaluate_real_parameter(intensity) - 1.0) < 0.0001
                        and abs(self._evaluate_real_parameter(modulation_factor)) < 0.0001
                    )

            if unmodulated:
                target = self._material_shader_path("decals", "base_tint")
            elif selected_tinting in {"partially_modulated", "fully_modulated"}:
                target = self._material_shader_path("decals", "base_modulated_tint")
                if selected_tinting == "fully_modulated":
                    self._add_real_parameter(material, "tint_modulation_factor", 1.0)
            else:
                result = False

        self._set_material_shader_reference(material, target)
        return result

    def _set_material_shader_from_screen_shader(self, material: MaterialTag, shader: ShaderTag) -> bool:
        result = True
        selected_warp = self._selected_option(shader, "warp")
        selected_base = self._selected_option(shader, "base")
        selected_overlay_a = self._selected_option(shader, "overlay_a")
        selected_overlay_b = self._selected_option(shader, "overlay_b")

        target = self._material_shader_path("screen", "base")
        if selected_warp == "screen_space":
            if selected_overlay_a == "none" and selected_overlay_b == "none":
                target = self._material_shader_path("screen", "base")
            elif selected_overlay_a == "detail_screen_space" and selected_overlay_b == "tint_add_color":
                target = self._material_shader_path("screen", "screen_detail_tint")
            elif selected_overlay_a == "detail_screen_space" and selected_overlay_b == "none":
                target = self._material_shader_path("screen", "screen_detail")
            else:
                result = False
        elif selected_warp == "none":
            if selected_base == "single_screen_space":
                if selected_overlay_a == "none" and selected_overlay_b == "tint_add_color":
                    target = self._material_shader_path("screen", "tint_alpha")
                elif selected_overlay_a == "tint_add_color" and selected_overlay_b == "none":
                    target = self._material_shader_path("screen", "tint_additive")
                elif selected_overlay_a == "detail_screen_space" and selected_overlay_b == "none":
                    target = self._material_shader_path("screen", "detail")
                else:
                    result = False
            elif selected_base == "normal_map_edge_shade":
                target = self._material_shader_path("screen", "tint_alpha_normal_map")
            else:
                result = False
        else:
            result = False

        self._set_material_shader_reference(material, target)
        return result

    def _set_material_shader_from_shader(self, material: MaterialTag, shader: ShaderTag, shader_group: str) -> bool:
        if shader_group == ".shader_decal":
            return self._set_material_shader_from_decal_shader(material, shader)
        if shader_group == ".shader_terrain":
            self._set_material_shader_reference(material, self._material_shader_path("materials", "srf_ca_layered_three_height_detailnormal"))
            return True
        if shader_group == ".shader_water":
            self._set_material_shader_reference(material, self._material_shader_path("materials", "water", "water"))
            return True
        if shader_group in {".shader_fur", ".shader_fur_stencil"}:
            self._set_material_shader_reference(material, self._material_shader_path("materials", "srf_lambert"))
            return True
        if shader_group == ".shader_screen":
            return self._set_material_shader_from_screen_shader(material, shader)

        result = True
        selected_albedo = self._selected_option(shader, "albedo")
        selected_material_model = self._selected_option(shader, "material_model")
        selected_alpha_test = self._selected_option(shader, "alpha_test")
        selected_reflection = self._selected_option(shader, "environment_mapping")
        selected_self_illum = self._selected_option(shader, "self_illumination")
        selected_specular_mask = self._selected_option(shader, "specular_mask")

        if shader_group == ".shader_halogram":
            selected_material_model = "none"
            selected_alpha_test = "none"
            selected_reflection = "none"

        if selected_material_model == "diffuse_only" and selected_albedo in {"constant_color", "default"}:
            albedo_color = self._parameter_by_name(shader, "albedo_color", 5)
            if albedo_color is not None:
                color = self._evaluate_color_parameter(albedo_color)
                if color is not None and sum(color[:3]) / 3.0 < 1.0 / 255.0:
                    selected_material_model = "none"

        if shader_group == ".shader_foliage":
            if selected_alpha_test == "simple":
                if selected_material_model == "specular":
                    target = self._material_shader_path("materials", "srf_foliage_clip_spec")
                else:
                    target = self._material_shader_path("materials", "srf_foliage_clip")
            else:
                target = self._material_shader_path("materials", "srf_foliage")
        elif selected_material_model in {"diffuse_only", "mikeshader"}:
            if selected_alpha_test == "simple":
                target = self._material_shader_path("materials", "srf_lambert_clip")
            else:
                target = self._material_shader_path("materials", "srf_lambert")
        elif selected_material_model in {"cook_torrance", "two_lobe_phong", "mid_blinn"}:
            if selected_reflection == "none":
                if selected_self_illum == "plasma":
                    target = self._material_shader_path("materials", "srf_blinn_twotone_plasma")
                else:
                    target = self._material_shader_path("materials", "srf_blinn_twotone_detail")
            elif selected_self_illum == "plasma":
                target = self._material_shader_path("materials", "srf_blinn_twotone_plasma_reflection")
            else:
                target = self._material_shader_path("materials", "srf_blinn_twotone_detail_reflection")
        elif selected_material_model == "foliage":
            if selected_alpha_test == "simple":
                target = self._material_shader_path("materials", "srf_foliage_clip")
            else:
                target = self._material_shader_path("materials", "srf_foliage")
        elif selected_material_model in {"hair", "organism"}:
            target = self._material_shader_path("materials", "srf_lambert")
        elif selected_material_model == "mid_skin":
            target = self._material_shader_path("materials", "srf_skin_simple")
        elif selected_material_model == "none":
            if selected_self_illum == "plasma":
                target = self._material_shader_path("materials", "srf_plasma")
            else:
                target = self._material_shader_path("materials", "srf_constant")
        else:
            target = self._material_shader_path("materials", "srf_lambert")
            result = False

        self._set_material_shader_reference(material, target)

        if selected_specular_mask == "specular_mask_from_diffuse":
            self._add_real_parameter(material, "diffuse_alpha_mask_specular", 1.0)

        return result

    def _set_material_physics_from_shader(self, material: MaterialTag, shader: ShaderTag, shader_group: str):
        physics, physics_2, physics_3, physics_4 = self._physics_from_reference(shader, shader_group)

        if not physics:
            physics = "default_material"
    
        material.tag.SelectField("StringId:physics material name").SetStringData(physics)
        material.tag.SelectField("StringId:physics material name 2").SetStringData(physics_2)
        material.tag.SelectField("StringId:physics material name 3").SetStringData(physics_3)
        material.tag.SelectField("StringId:physics material name 4").SetStringData(physics_4)

    def _physics_from_reference(self, shader: ShaderTag, shader_group: str) -> str:
        physics = ""
        physics_2 = ""
        physics_3 = ""
        physics_4 = ""
        if shader_group in {".shader", ".shader_halogram"}:
            physics = shader.tag.SelectField("material name").GetStringData()
        elif shader_group == ".shader_terrain":
            physics = shader.tag.SelectField("material name 0").GetStringData()
            physics_2 = shader.tag.SelectField("material name 1").GetStringData()
            physics_3 = shader.tag.SelectField("material name 2").GetStringData()
            physics_4 = shader.tag.SelectField("material name 3").GetStringData()

        if not physics and shader.reference.Path is not None and shader.path_exists(shader.reference.Path):
            with ShaderTag(path=shader.reference.Path) as reference_shader:
                return self._physics_from_reference(reference_shader, shader_group)
            
        return physics, physics_2, physics_3, physics_4

    def _set_blend_mode(self, material: MaterialTag, shader: ShaderTag, shader_group: str):
        if shader_group == ".shader_glass":
            material.alpha_blend_mode.SetValue("alpha_blend")
            return

        selected_blend = self._selected_option(shader, "blend_mode")
        if not selected_blend:
            selected_blend = "opaque"
        material.alpha_blend_mode.SetValue(selected_blend)

    def _set_material_shader_parameters_from_shader(self, material: MaterialTag, shader: ShaderTag) -> bool:
        result = True
        for shader_parameter in shader.block_parameters.Elements:
            parameter_name = shader_parameter.Fields[0].GetStringData()
            parameter_type = int(shader_parameter.Fields[1].Value)

            if parameter_type == 0:
                target = BITMAP_PARAMETER_REMAP.get(parameter_name)
                bitmap = shader_parameter.SelectField("bitmap")
                if target and bitmap.Path is not None:
                    result &= self._convert_bitmap_parameter(material, shader_parameter, target)
                elif target:
                    print(f"    skipped invalid bitmap reference: {parameter_name}")
            elif parameter_type in {1, 5}:
                target_names = COLOR_PARAMETER_REMAP.get(parameter_name)
                if target_names:
                    result &= self._convert_color_parameter(material, shader_parameter, *target_names)
            elif parameter_type == 2:
                result &= self._convert_real_by_name(material, shader, shader_parameter, parameter_name)

        return result

    def _convert_bitmap_parameter(self, material: MaterialTag, shader_parameter, target_parameter_name: str) -> bool:
        result = True
        material_parameter = self._add_material_parameter(material, target_parameter_name, "bitmap")
        material_parameter.SelectField("bitmap").Path = shader_parameter.SelectField("bitmap").Path

        for name in (
            "bitmap flags",
            "bitmap filter mode",
            "bitmap address mode",
            "bitmap address mode x",
            "bitmap address mode y",
            "bitmap sharpen mode",
        ):
            material_parameter.SelectField(name).Data = shader_parameter.SelectField(name).Data

        # result &= self._remap_bitmap_extern_mode(shader_parameter, material_parameter)

        animated_parameters = shader_parameter.SelectField("Block:animated parameters")
        for animated_parameter in animated_parameters.Elements:
            animated_type = self._animated_parameter_type(animated_parameter)
            self._add_function_to_material_parameter(material_parameter, animated_parameter, animated_type)

        return result

    # def _remap_bitmap_extern_mode(self, shader_parameter, material_parameter) -> bool:
    #     source = shader_parameter.SelectField("bitmap extern mode")
    #     target = material_parameter.SelectField("bitmap extern mode")
    #     source_items = [i.EnumName for i in source.Items]
    #     source_name = source_items[source.Value]
    #     if source_name in BITMAP_EXTERN_UNSUPPORTED:
    #         return False
    #     target.SetValue(BITMAP_EXTERN_REMAP.get(source_name, "none"))
    #     return True

    def _convert_color_parameter(
        self,
        material: MaterialTag,
        shader_parameter,
        target_parameter_name: str,
        target_parameter_name_2: str | None = None,
        target_parameter_name_3: str | None = None,
    ) -> bool:
        result = True
        color_function = None
        alpha_function = None
        animated_parameters = shader_parameter.SelectField("Block:animated parameters")

        for animated_parameter in animated_parameters.Elements:
            animated_type = self._animated_parameter_type(animated_parameter)
            if animated_type == 1:
                color_function = animated_parameter
            elif target_parameter_name_2 and animated_type == 8:
                alpha_function = animated_parameter

        if color_function is not None:
            if target_parameter_name_2 and target_parameter_name_3:
                self._add_color_parameter(material, target_parameter_name, self._function_color(color_function, 0))
                self._add_color_parameter(material, target_parameter_name_2, self._function_color(color_function, 1))
                self._add_real_parameter(material, target_parameter_name_3, self._function_exponent(color_function))
            else:
                self._add_material_function_parameter(material, target_parameter_name, "color", color_function)

        if alpha_function is not None and target_parameter_name_2 and not target_parameter_name_3:
            self._add_material_function_parameter(material, target_parameter_name_2, "real", alpha_function)

        return result

    def _convert_real_by_name(self, material: MaterialTag, shader: ShaderTag, shader_parameter, parameter_name: str) -> bool:
        result = True
        if parameter_name == "roughness":
            has_power_parameter = any(
                self._parameter_by_name(shader, name, 2) is not None
                for name in ("normal_specular_power", "specular_power", "glancing_specular_power")
            )
            if not has_power_parameter:
                result &= self._convert_real_parameter(
                    material, shader_parameter, "specular_power_min", self._convert_roughness_to_specular_power
                )
                result &= self._convert_real_parameter(
                    material, shader_parameter, "specular_power_max", self._convert_roughness_to_specular_power
                )
        elif parameter_name in {"normal_specular_power", "specular_power"}:
            result &= self._convert_real_parameter(material, shader_parameter, "specular_power_max", self._convert_specular_power)
        elif parameter_name == "glancing_specular_power":
            result &= self._convert_real_parameter(material, shader_parameter, "specular_power_min", self._convert_specular_power)
        elif parameter_name in {"albedo_blend", "0_plastic_1_metal"}:
            result &= self._convert_real_parameter(material, shader_parameter, "specular_mix_albedo")
            result &= self._convert_real_parameter(material, shader_parameter, "diffuse_mask_reflection")
        elif parameter_name.startswith("thinness_"):
            result &= self._convert_real_parameter(material, shader_parameter, parameter_name)
        elif parameter_name in REAL_PARAMETER_DIRECT:
            result &= self._convert_real_parameter(material, shader_parameter, REAL_PARAMETER_DIRECT[parameter_name])

        return result

    def _convert_real_parameter(self, material: MaterialTag, shader_parameter, target_parameter_name: str, convert_function=None) -> bool:
        animated_parameters = shader_parameter.SelectField("Block:animated parameters")
        first_animated = next(iter(animated_parameters.Elements), None)
        if first_animated is not None:
            if convert_function is None:
                self._add_material_function_parameter(material, target_parameter_name, "real", first_animated)
            else:
                self._add_real_parameter(material, target_parameter_name, convert_function(first_animated.SelectField("animation function").Value.ClampRangeMin))
        else:
            value = shader_parameter.SelectField("real").Data
            if convert_function is not None:
                value = convert_function(value)
            self._add_real_parameter(material, target_parameter_name, value)
        return True

    def _set_material_shader_parameter_defaults(self, material: MaterialTag, shader: ShaderTag):
        material_shader_path = material.reference_material_shader.Path
        material_shader_name = material_shader_path.RelativePath if material_shader_path is not None else ""
        if "srf_constant" not in material_shader_name:
            return
        has_si_color = (
            self._parameter_by_name(shader, "self_illum_color", 1) is not None
            or self._parameter_by_name(shader, "self_illum_color", 5) is not None
        )
        if not has_si_color:
            self._add_color_parameter(material, "si_color", [1.0, 1.0, 1.0, 1.0])

    def _set_material_flags(self, material: MaterialTag, shader: ShaderTag, shader_group: str):
        if shader_group == ".shader_decal":
            if self._selected_option(shader, "render_pass") == "post_lighting":
                material.tag.SelectField("WordFlags:flags").SetBit("decal post lighting", True)
        elif shader_group == ".shader_screen":
            if shader.render_method.SelectField("WordFlags:shader flags").TestBit("resolve screen"):
                material.tag.SelectField("WordFlags:render flags").SetBit("resolve screen", True)

    def _set_additional_material_properties(self, material: MaterialTag, shader: ShaderTag, shader_group: str):
        if shader_group != ".shader_screen":
            return
        material.tag.SelectField("sort offset").Data = shader.render_method.SelectField("sort order").Data
        material.tag.SelectField("sort layer").Data = shader.render_method.SelectField("render layer").Data

    def _fix_materials(self, material: MaterialTag):
        path = material.reference_material_shader.Path
        if path is None or _norm(path.RelativePathWithExtension) != _norm(
            self._material_shader_path("materials", "srf_constant") + ".material_shader"
        ):
            return

        wireframe = self._material_parameter(material, "wireframe_outline")
        if wireframe is None:
            return
        if not bool(wireframe.SelectField(r"int\bool").Data):
            return

        with MaterialShaderTag(path=path) as material_shader:
            if "wireframe_outline" not in material_shader.read_parameters_list():
                return

        self._set_material_shader_reference(material, self._material_shader_path("materials", "srf_constant_wireframe"))

    def _add_material_parameter(self, material: MaterialTag, parameter_name: str, parameter_type: str):
        element = self._material_parameter(material, parameter_name, parameter_type)
        if element is None:
            element = material.block_parameters.AddElement()
            element.SelectField("parameter name").SetStringData(parameter_name)
            element.SelectField("parameter type").SetValue(parameter_type)
        else:
            element.SelectField("parameter type").SetValue(parameter_type)
        return element

    def _material_parameter(self, material: MaterialTag, parameter_name: str, parameter_type: str | None = None):
        wanted = _norm(parameter_name)
        for element in material.block_parameters.Elements:
            name = element.Fields[0].GetStringData()
            if _norm(name) != wanted:
                continue
            if parameter_type is None:
                return element
            ptype = element.SelectField("parameter type")
            ptype_items = [i.EnumName for i in ptype.Items]
            ptype_name = ptype_items[ptype.Value]
            if ptype_name == parameter_type:
                return element
            return element
        return None

    def _add_real_parameter(self, material: MaterialTag, parameter_name: str, parameter_value: float):
        element = self._add_material_parameter(material, parameter_name, "real")
        element.SelectField("real").Data = float(parameter_value)
        element.SelectField("vector").Data = [float(parameter_value), 0.0, 0.0]
        return element

    def _add_color_parameter(self, material: MaterialTag, parameter_name: str, argb_color):
        element = self._add_material_parameter(material, parameter_name, "color")
        element.SelectField("color").Data = list(argb_color)
        return element

    def _add_material_function_parameter(self, material: MaterialTag, parameter_name: str, parameter_type: str, shader_function):
        material_parameter = self._add_material_parameter(material, parameter_name, parameter_type)
        target_type = 1 if parameter_type == "color" else 0
        self._add_function_to_material_parameter(material_parameter, shader_function, target_type)

        return material_parameter

    def _add_function_to_material_parameter(self, material_parameter, shader_function, target_type: int):
        block = material_parameter.SelectField("Block:function parameters")
        material_function = block.AddElement()
        material_function.SelectField("type").Value = target_type

        input_name = shader_function.SelectField("input name").GetStringData()
        range_name = shader_function.SelectField("range name").GetStringData()
        material_function.SelectField("input name").SetStringData(input_name)
        material_function.SelectField("range name").SetStringData(range_name)
        material_function.SelectField("time period").Data = shader_function.SelectField("time period").Data
        source_function = shader_function.SelectField("animation function")
        target_function = material_function.SelectField("function")
        target_function.Deserialize(source_function.Serialize())
        
        if target_type == 1:
            self._copy_function_colors(source_function.Value, target_function.Value)
            material_parameter.SelectField("color").Data = self._function_color(shader_function, 0)
        else:
            value = source_function.Value.ClampRangeMin
            if target_type in {2, 3}:
                material_parameter.SelectField("real").Data = value
            if target_type in {2, 4}:
                material_parameter.SelectField("vector").Data[0] = value
            elif target_type == 5:
                material_parameter.SelectField("vector").Data[1] = value
            elif target_type == 6:
                material_parameter.SelectField("vector").Data[2] = value

        return material_function

    def _copy_function_colors(self, source_editor, target_editor):
        target_editor.MasterType = source_editor.MasterType
        target_editor.ColorGraphType = source_editor.ColorGraphType

        color_count = max(1, min(int(source_editor.ColorCount), 4))
        for color_index in range(color_count):
            game_color = source_editor.GetColor(color_index)
            if game_color.ColorMode == 1:
                game_color = game_color.ToRgb()
            target_editor.SetColor(color_index, game_color)

    def _selected_option(self, shader: ShaderTag, category_name: str) -> str:
        categories = self._definition_categories(shader)
        wanted = _norm(category_name)
        for category_index, (category, options) in enumerate(categories):
            if _norm(category) != wanted:
                continue
            option_index = self._option_value_from_index(shader, category_index)
            if 0 <= option_index < len(options):
                return _norm(options[option_index])
            return ""
        return ""

    def _definition_categories(self, shader: ShaderTag) -> list[tuple[str, list[str]]]:
        definition_path = shader.definition.Path if shader.definition else None
        if definition_path is None:
            return []
        cache_key = definition_path.RelativePathWithExtension.lower()
        cached = self.definition_cache.get(cache_key)
        if cached is not None:
            return cached

        categories: list[tuple[str, list[str]]] = []
        if not self._tagpath_exists_in_current_project(definition_path):
            warning = f"Missing render method definition: {definition_path.RelativePathWithExtension}"
            self.report.warnings.append(warning)
            print(f"*** {warning}")
            self.definition_cache[cache_key] = categories
            return categories

        with RenderMethodDefinitionTag(path=definition_path, tag_must_exist=True) as definition:
            for category_element in definition.block_categories.Elements:
                category_name = category_element.Fields[0].GetStringData()
                option_block = category_element.Fields[1]
                options = [option.Fields[0].GetStringData() for option in option_block.Elements]
                categories.append((category_name, options))

        self.definition_cache[cache_key] = categories
        return categories

    def _option_value_from_index(self, shader: ShaderTag, index: int) -> int:
        option_value = int(shader.block_options.Elements[index].Fields[0].Data)
        if option_value == -1 and shader.reference.Path is not None and shader.path_exists(shader.reference.Path):
            with ShaderTag(path=shader.reference.Path) as reference_shader:
                return self._option_value_from_index(reference_shader, index)
        return max(option_value, 0)

    def _parameter_by_name(self, shader: ShaderTag, parameter_name: str, parameter_type: int | None = None):
        wanted = _norm(parameter_name)
        for element in shader.block_parameters.Elements:
            name = element.Fields[0].GetStringData()
            if _norm(name) != wanted:
                continue
            if parameter_type is not None and int(element.Fields[1].Value) != parameter_type:
                continue
            return element
        return None

    def _animated_parameter_type(self, animated_parameter) -> int:
        return int(animated_parameter.SelectField("type").Value)

    def _evaluate_real_parameter(self, shader_parameter) -> float:
        animated_parameters = shader_parameter.SelectField("Block:animated parameters")
        for animated_parameter in animated_parameters.Elements:
            if self._animated_parameter_type(animated_parameter) == 0:
                return animated_parameter.SelectField("animation function").Value.ClampRangeMin
        return float(shader_parameter.SelectField("real").Data)

    def _evaluate_color_parameter(self, shader_parameter):
        animated_parameters = shader_parameter.SelectField("Block:animated parameters")
        for animated_parameter in animated_parameters.Elements:
            if self._animated_parameter_type(animated_parameter) == 1:
                color = self._function_color(animated_parameter, 0)
                return [color[1], color[2], color[3]]
        return None

    def _function_color(self, animated_parameter, color_index: int):
        editor = animated_parameter.SelectField("animation function")
        game_color = editor.Value.GetColor(color_index)
        if game_color.ColorMode == 1:
            game_color = game_color.ToRgb()
        return [game_color.Alpha, game_color.Red, game_color.Green, game_color.Blue]

    def _function_exponent(self, animated_parameter) -> float:
        editor = animated_parameter.SelectField("animation function")
        exponent = float(editor.Value.GetExponent(0))
        return 1.0 if abs(exponent) < 0.0001 else exponent

    def _convert_specular_power(self, power: float) -> float:
        if abs(power) < 0.000001:
            return 0.0
        return 1.0 / power

    def _convert_roughness_to_specular_power(self, roughness: float) -> float:
        roughness = max(float(roughness), 0.000001)
        direct_power = max((2.0 / (roughness * roughness)) - 2.0, 0.000001)
        return self._convert_specular_power(direct_power)


class NWO_OT_ShaderToMaterial(bpy.types.Operator):
    bl_idname = "nwo.shader_to_material"
    bl_label = "Convert Shaders to Materials"
    bl_description = "Converts scoped legacy shader tags to material tags using the H4 Tool shader-to-material rules"
    bl_options = {"UNDO"}

    scope: bpy.props.EnumProperty(
        name="Scope",
        items=[
            ("BLEND", "From Blend", "Runs only on shader paths set on materials in this blender file"),
            ("PATH", "File / Folder", "Runs on a specific shader tag or folders set here"),
            ("ALL", "All Shaders", "Runs on every supported shader tag in your project tags directory"),
        ],
    )

    path: bpy.props.StringProperty(
        name="Path",
        description="Path to a single shader or directory containing shaders. The path can be full or tag relative",
    )

    delete_shaders: bpy.props.BoolProperty(
        name="Delete Shader Tags",
        description="Delete successfully converted source shader tags from the current project after material tags are written",
        default=False,
    )

    @classmethod
    def poll(cls, context):
        return utils.current_project_valid() and utils.is_corinth(context)

    def execute(self, context):
        os.system("cls")
        scene_nwo_export = utils.get_export_props()
        if scene_nwo_export.show_output:
            bpy.ops.wm.console_toggle()

        print("Converting Shaders to Materials\n")
        start = time.perf_counter()

        converter = ShaderToMaterialConverter(delete_shaders=self.delete_shaders)
        converter.prepare_shader_paths_for_gather(self.scope, self.path)
        shader_paths = converter.gather_shader_paths(self.scope, self.path)

        print(f"--- Found {len(shader_paths)} supported shader paths in scope")
        if not shader_paths:
            self.report({"WARNING"}, "No shader paths in scope")
            return {"FINISHED"}

        with utils.ExportManager():
            report = converter.convert_paths(shader_paths, update_blend_references=self.scope == "BLEND")

        end = time.perf_counter()
        print("\n-----------------------------------------------------------------------")
        print(
            f"{report.converted} created, {report.updated} updated, {report.skipped} skipped, "
            f"{report.failed} failed in {utils.human_time(end - start, True)}"
        )
        if report.unsupported:
            print(f"{report.unsupported} unsupported shader tags skipped")
        if report.imported:
            print(f"{report.imported} external shader tags copied into this project's tags\\_temp folder")
        if report.dependencies_copied:
            print(f"{report.dependencies_copied} external dependency tags copied into this project")
        if report.deleted:
            print(f"{report.deleted} source shader tags deleted")
        print("-----------------------------------------------------------------------")

        if report.failed:
            self.report({"WARNING"}, f"Converted with {report.failed} failure(s). See console for details")
        else:
            message = f"Converted {report.converted + report.updated} shader tag(s) to material tags"
            if report.deleted:
                message += f"; deleted {report.deleted} shader tag(s)"
            self.report({"INFO"}, message)
        return {"FINISHED"}

    def invoke(self, context, _):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "scope", expand=True)
        if self.scope == "PATH":
            layout.prop(self, "path")
        layout.prop(self, "delete_shaders")


def shader_to_material(shader_path: str) -> str:
    converter = ShaderToMaterialConverter()
    return converter.convert_shader(shader_path)
