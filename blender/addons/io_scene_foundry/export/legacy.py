"""JMS/ASS backend for Foundry's prepared VirtualScene.

The normal export path owns evaluation, filtering, triangulation, face overrides,
animation sampling and restoration. This adapter only converts that result into
the reusable legacy format models and writes files below the data asset folder.
"""
from ..exceptions import ExportCancelled
from ..patches import ToolPatcher
from collections import defaultdict
from contextlib import nullcontext
from copy import copy
from datetime import datetime
from getpass import getuser
from math import degrees
from pathlib import Path
from tempfile import NamedTemporaryFile
import io
import json
import os
import re
import subprocess
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import bpy
from mathutils import Matrix, Quaternion, Vector

from .process import ExportScene
from .cinematic import CinematicScene, set_actor_animation_compression
from .legacy_materials import material_variant
from .halo2_water import water_plane_height
from .cleanup import ANIMATION_EXTENSIONS, prune_intermediates
from .shader_collections import ShaderCollections, halo1_shader_lookup
from ..legacy import jms_format as jms
from ..legacy import ass_format as ass
from ..legacy.seam_geometry import ass_seam_triangles
from ..legacy.mirror import mirror_ass, mirror_jms, mirror_transform
from ..legacy.mesh_geometry import clean_ass_mesh
from ..legacy.import_info import FRAME_PREFIXES
from ..legacy.lighting import jms_emissive_unsupported
from ..legacy.references import ASS_GAMES, ASS_GAME_OBJECT_EXTENSIONS, ass_reference_name, ass_reference_prefix
from ..legacy.writers import VERSIONS, TextWriter, hierarchy, legacy_bone_order, node_checksum, write_jms, write_ass
from ..tags.backend import TagDocument
from ..tags.halo2_water import water_settings, write_water_definition
from ..tags.sky import SkyDocument, SkyLightRecord, MAX_SKY_LIGHTS
from ..tags.halo1_emissive import (asset_shader_folder, localize_shader_environment,
                                 shader_environment_path,
                                 write_material_emissive)
from ..tags.halo1_shader_paths import (INVALID_SHADER_PATH, ensure_invalid_shader,
                                      shader_import_paths, repair_shader_references)
from ..tags.halo1_shader_conversion import convert_shader
from ..tags.animation_graph import AnimationGraphTag
from ..tags.render_model import RenderModelMetadataTag
from ..tags.model_blender import ModelTag
from ..tags.object import ObjectDocument
from ..tags.scenario import ScenarioDocument
from ..tags.seams import StructureSeamsDocument
from ..tags.structure_design import StructureDesignDocument
from ..tools.scenario.lightmap import run_halo1_lightmapper, run_lightmapper
from .. import utils, foundry_output


def legacy_instance_name(name: str, props: dict, mesh_type: int,
                         target_game: str | None = None) -> str:
    """Encode pre-Reach instanced-geometry policies in the ASS instance name."""
    if target_game in {'halo3', 'halo3odst'} and mesh_type == 18:
        # Tool identifies design-water geometry by its instance prefix.
        return '~' + name.lstrip('~')
    prefix = {4: '%', 5: '@', 6: '$', 11: '%'}.get(mesh_type, '')
    base_name = name.lstrip('%@$')
    if mesh_type != 4:
        if not prefix and (base_name.split(':', 1)[0].casefold() == 'frame'
                           or base_name.casefold().startswith(FRAME_PREFIXES)):
            # Imported export frames can also carry geometry. After flattening,
            # their mesh is a sibling of the other surfaces, not their parent.
            # Tool must not select that mesh as a new export hierarchy root.
            base_name = 'mesh ' + base_name
        return prefix + base_name

    # Imported names already contain the source policy symbols. Rebuild them
    # from the current properties once, so editing a policy can clear it too.
    base_name = base_name.lstrip('+-!?*>&^<|')

    pathfinding = {0: '-', 2: '+'}.get(props.get('bungie_mesh_poop_pathfinding'), '')
    lighting = {1: '>', 2: '!', 3: '?'}.get(props.get('bungie_mesh_poop_lighting'), '')
    flags = ''.join((
        '*' if props.get('bungie_mesh_poop_is_render_only') else '',
        '&' if props.get('bungie_mesh_poop_chops_portals') else '',
        '^' if props.get('bungie_mesh_poop_does_not_block_aoe') else '',
        '<' if props.get('bungie_mesh_poop_excluded_from_lightprobes') else '',
        '|' if props.get('bungie_mesh_poop_decal_spacing') else '',
    ))
    return '%' + pathfinding + lighting + flags + base_name


def filename(name):
    if not name or name in {'.', '..'} or any(c in name for c in '<>:"/\\|?*\r\n') or name.endswith((' ', '.')):
        raise ExportCancelled(f'Invalid legacy export filename: {name!r}')
    return name


def jmi_text(version: int, children: list[str]) -> str:
    """Serialize the small manifest consumed by H2 bulk asset importers."""
    if version < 8207:
        raise ExportCancelled(f'JMI is unavailable for JMS version {version}')
    if not children:
        raise ExportCancelled('JMI requires at least one child model')
    return '\n'.join((str(version), str(len(children)), *children, ''))


def transform(matrix, scale=1, inverse_rotation=False):
    rotation = matrix.to_quaternion()
    if inverse_rotation:
        rotation.invert()
    return jms.Transform((rotation.x, rotation.y, rotation.z, rotation.w), tuple(c * scale for c in matrix.translation))


def write_outputs(outputs, *, maya_order=False):
    """Stage the whole batch before replacing any existing file."""
    outputs = list(outputs)
    staged = []
    process = '--- Writing Intermediary Files'
    try:
        with utils.Spinner():
            utils.update_job_count(process, '', 0, len(outputs))
            for index, (path, asset) in enumerate(outputs, 1):
                foundry_output._raise_if_cancel_requested()
                path.parent.mkdir(parents=True, exist_ok=True)
                with NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n', dir=path.parent,
                                        prefix=path.name + '.', suffix='.tmp', delete=False) as stream:
                    temporary = Path(stream.name)
                    staged.append((temporary, path))
                    if isinstance(asset, jms.JMS):
                        write_jms(asset, stream, maya_order=maya_order)
                    elif isinstance(asset, ass.ASS):
                        # Match the Max ASS writer's fixed decimal precision.
                        # Significant-digit formatting truncates large BSP
                        # translations and changes portal-plane arithmetic.
                        write_ass(asset, stream, decimal_places=10)
                    else:
                        stream.write(asset)
                if index < len(outputs):
                    utils.update_job_count(process, '', index, len(outputs))
            # Honour a request received during the final serialization or
            # before replacing any existing intermediate files.
            foundry_output._raise_if_cancel_requested()
            for temporary, path in staged:
                temporary.replace(path)
            utils.update_job_count(process, '', len(outputs), len(outputs))
    finally:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)


def ensure_asset_marker(asset_path: Path, data_dir: Path, scene_settings) -> Path:
    """Create the small sidecar used to identify an H1-ODST asset folder."""
    marker = asset_path / f'{asset_path.name}.sidecar.xml'
    scene_settings.sidecar_path = str(marker.relative_to(data_dir))
    if marker.is_file():
        return marker

    metadata = ET.Element('Metadata')
    header = ET.SubElement(metadata, 'Header')
    values = {
        'MainRev': '0',
        'PointRev': '6',
        'Description': 'Forged in Foundry',
        'Created': datetime.today().strftime('%Y-%m-%d %H:%M:%S'),
        'By': getuser(),
        'DirectoryType': 'TAE.Shared.NWOAssetDirectory',
        'Schema': '1',
        'SourceBlend': utils.relative_path(bpy.data.filepath) if bpy.data.filepath else '',
        'BlenderVersion': bpy.app.version_string,
        'FoundryVersion': utils.get_version_string(),
        'AnimationOnly': str(scene_settings.asset_type == 'animation'),
    }
    for name, value in values.items():
        ET.SubElement(header, name).text = value
    ET.SubElement(metadata, 'FaceCollections')

    marker.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode='wb', dir=marker.parent,
                            prefix=marker.name + '.', suffix='.tmp',
                            delete=False) as stream:
        temporary = Path(stream.name)
        ET.ElementTree(metadata).write(stream, encoding='utf-8',
                                       xml_declaration=True)
    try:
        temporary.replace(marker)
    finally:
        temporary.unlink(missing_ok=True)
    print(f'--- Created asset marker: {marker}')
    return marker


class LegacyExportScene(ExportScene):
    legacy_export = True

    object_tag_types = (
        'biped', 'crate', 'creature', 'device_control', 'device_machine',
        'device_terminal', 'effect_scenery', 'equipment', 'giant', 'scenery',
        'vehicle', 'weapon',
    )

    @property
    def supported_object_tag_types(self):
        unsupported = ({'crate', 'device_terminal', 'effect_scenery', 'giant'} if self.target_game == 'halo1'
                       else {'device_terminal', 'effect_scenery', 'giant'} if self.target_game == 'halo2'
                       else set())
        return tuple(tag_type for tag_type in self.object_tag_types if tag_type not in unsupported)

    def __init__(self, *args, **kwargs):
        self.original_cwd = Path.cwd()
        try:
            super().__init__(*args, **kwargs)
        except Exception:
            os.chdir(self.original_cwd)
            raise
        self.target_game = utils.get_project(self.scene_settings.scene_project).game
        self.halo2_water_settings = {}
        self.jms_version, self.ass_version, self.jma_version = VERSIONS[self.target_game]
        self.shader_collections = ShaderCollections(self.tags_dir, self.target_game)
        self.granny_textures = False
        self.warned_shader_paths = set()
        self.shader_name_cache = {}
        self.halo1_two_sided_shaders = set()
        self.halo1_shader_paths = {}
        self.skipped_legacy_animations = set()

    def export_legacy(self, single_animation=False):
        self.bones = []
        skeleton = self.virtual_scene.skeleton_model
        if skeleton:
            self.bones = [b for b in skeleton.skeleton.bones if isinstance(b.bone, bpy.types.PoseBone)]
            by_name = {b.name: b for b in self.bones}
            parents = {
                b.name: skeleton.skeleton.bones[b.parent_index].name if b.parent_index >= 0 else None
                for b in self.bones
            }
            self.bones = [by_name[name] for name in legacy_bone_order(parents)]
        self.bone_index = {b.name: i for i, b in enumerate(self.bones)}
        self.bone_world = {b.name: b.matrix_world for b in self.bones}
        self.bone_parents = {}
        if skeleton:
            for bone in self.bones:
                parent = skeleton.skeleton.bones[bone.parent_index] if bone.parent_index >= 0 else None
                self.bone_parents[bone.name] = self.bone_index.get(parent.name, -1) if parent else -1
        grouped = defaultdict(list)
        markers = []
        for node in self.virtual_scene.nodes.values():
            foundry_output._raise_if_cancel_requested()
            if node.invalid:
                continue
            if node.props.get('bungie_object_type') == 2:
                if (not single_animation and ('markers' in self.export_tag_types or self.supports_bsp) and
                        self.jms_version < 8201 and
                        node.ob.nwo.marker_type == '_connected_geometry_marker_type_game_instance'):
                    self.warnings.append(f'{node.name}: H1 JMS cannot encode tag-reference markers. Skipping marker')
                    continue
                markers.append(node)
            if node.mesh is None or node.mesh.invalid:
                continue
            if self.limit_bsps_to_selection and node.region not in self.selected_bsps:
                continue
            if self.limit_perms_to_selection and node.permutation not in self.selected_permutations and node.props.get('bungie_mesh_type') != 11:
                continue
            if node.props.get('bungie_mesh_type') == 11 and self.ass_version is None:
                self.warnings.append(f'{node.name}: H1 does not support ASS model instances. Skipping mesh')
                continue
            if node.tag_type not in self.export_tag_types:
                continue
            folder = {'design': 'structure', 'structure': 'structure', 'render': 'render',
                      'collision': 'collision', 'physics': 'physics'}.get(node.tag_type)
            if folder is None:
                self.warnings.append(f'{node.name}: unsupported legacy geometry role {node.tag_type}. Skipping mesh')
                continue
            if self.target_game == 'halo1':
                # H1 Tool scans ``models`` for render geometry and ``physics``
                # for the JMS used by both collision-geometry and physics.
                folder = {'render': 'models', 'collision': 'physics',
                          'physics': 'physics'}.get(folder, folder)
            name = node.region if folder == 'structure' else node.permutation or 'default'
            if folder == 'collision' and self.target_game in {'halo3', 'halo3odst'}:
                # H3 collision import info can share vertices between several
                # permutations in one JMS. Splitting files changes Tool's weld
                # candidates and can move clipped collision boundaries.
                name = 'default'
            if folder == 'render' and self.target_game in {'halo3', 'halo3odst'}:
                # Material records carry permutations within a shared render file.
                name = 'default'
            if self.target_game == 'halo2' and folder == 'render' and node.props.get('bungie_mesh_type') != 11:
                # Tool consumes LOD labels per material, but still requires
                # separate source meshes/files to avoid overlapping strips.
                name = node.ob.nwo.mesh_lod + '_' + name
            if self.target_game == 'halo1' and folder == 'models':
                # H1 Tool takes the LOD from the JMS filename, not materials.
                lod_names = {'L1': 'superlow', 'L2': 'low', 'L3': 'medium',
                             'L4': 'high', 'L5': 'superhigh'}
                lod = node.ob.nwo.mesh_lod
                if lod not in lod_names:
                    self.warnings.append(f'{node.name}: Halo 1 does not support LOD {lod}. Skipping mesh')
                    continue
                name = f'{name} {lod_names[lod]}'
            if node.tag_type == 'design' and self.target_game not in {'halo1', 'halo2'}:
                name += '_design'
            if node.props.get('bungie_mesh_type') == 11:
                nwo = node.ob.nwo
                listed = {p.name for p in nwo.marker_permutations}
                permutations = [p for p in self.permutations if not nwo.marker_uses_regions or not listed or
                                ((p in listed) != (nwo.marker_permutation_type == 'exclude'))]
                for permutation in permutations:
                    if self.limit_perms_to_selection and permutation not in self.selected_permutations:
                        continue
                    variant = copy(node)
                    variant.permutation = permutation
                    grouped[(folder, filename(permutation))].append(variant)
            else:
                grouped[(folder, filename(name))].append(node)
        if not single_animation and not grouped and (
                (self.bones and 'skeleton' in self.export_tag_types) or
                (markers and 'markers' in self.export_tag_types)):
            grouped[('models' if self.target_game == 'halo1' else 'render',
                     'default superhigh' if self.target_game == 'halo1' else 'default')] = []
        animations = [animation for animation in self.virtual_scene.animations
                      if hasattr(animation, 'legacy_tracks')]
        geometry_count = 0 if single_animation else len(grouped)
        if self.target_game == 'halo1' and geometry_count:
            ensure_invalid_shader(self.tags_dir)
            paths = [str(INVALID_SHADER_PATH), *(slot.material.nwo.shader_path
                     for ob in self.ob_halo_data
                     for slot in getattr(ob, 'material_slots', ())
                     if slot.material is not None)]
            for nodes in grouped.values():
                for node in nodes:
                    for material, _, _ in node.mesh.groups:
                        path = material.shader_path
                        shader_type = getattr(material, 'shader_type', '')
                        if shader_type.startswith('shader'):
                            paths.append(f'{path}.{shader_type}')
            self.shader_collections.reserve_halo1_paths(paths)
            self.shader_name_cache.clear()
        elif geometry_count and self.target_game in {'halo2', 'halo3', 'halo3odst'}:
            # Tool also looks up invalid when it needs its own fallback, even
            # when every exported material already has a valid shader.
            self.shader_collections.material_name(r'shaders\invalid.shader')
        preparation_count = geometry_count + len(animations)
        process = '--- Preparing Intermediary Files'
        with utils.Spinner():
            utils.update_job_count(process, '', 0, preparation_count)
            outputs = []
            if not single_animation:
                structure_names = {key_name for (key_folder, key_name) in grouped
                                   if key_folder == 'structure'}
                if len(structure_names) > 1:
                    for marker in markers:
                        if (marker.ob.nwo.marker_type == '_connected_geometry_marker_type_game_instance' and
                                marker.region not in structure_names):
                            raise ExportCancelled(
                                f'{marker.name}: assign this tag-reference marker to one of the '
                                f'exported BSPs ({", ".join(sorted(structure_names))})')
                uses_jmi = (self.target_game == 'halo2' and self.asset_type.name in {
                    'PARTICLE_MODEL', 'DECORATOR_SET'})
                jmi_children = []
                for index, ((folder, name), nodes) in enumerate(grouped.items()):
                    utils.update_job_count(process, '', index, preparation_count)
                    use_ass = self.ass_version is not None and (folder == 'structure' or
                        (folder == 'render' and any(n.props.get('bungie_mesh_type') == 11 for n in nodes)))
                    lights = (() if self.target_game in {'halo1', 'halo2'} else
                              tuple(ob for ob, bsp in self.lights.items()
                                    if folder == 'structure' and bsp == name))
                    ass_markers = ()
                    if folder == 'render':
                        ass_markers = markers
                    elif folder == 'structure':
                        ass_markers = tuple(marker for marker in markers
                                            if len(structure_names) == 1 or marker.region == name)
                    # Keep the actual permutation name for marker inclusion tests;
                    # the LOD suffix belongs only to the output filename.
                    asset_name = name
                    if self.target_game == 'halo1' and folder == 'models':
                        asset_name = (nodes[0].permutation or 'default') if nodes else 'default'
                    elif self.target_game == 'halo2' and folder == 'render' and nodes:
                        asset_name = nodes[0].permutation or 'default'
                    asset = (self.ass_asset(
                        asset_name, nodes, ass_markers, lights)
                        if use_ass else self.jms_asset(asset_name, nodes, markers, folder))
                    if self.mirror:
                        (mirror_ass if use_ass else mirror_jms)(asset)
                    if uses_jmi:
                        if folder != 'render' or use_ass:
                            raise ExportCancelled(
                                f'{self.asset_type.name.lower()} JMI children must be render JMS files')
                        child_name = (self.asset_name if len(grouped) == 1 else name)
                        child_name = filename(child_name)
                        jmi_children.append(child_name)
                        output_path = Path(
                            self.asset_path, child_name, 'render',
                            child_name + '.jms')
                    else:
                        # Keep the structure role for serialization, but H1 Tool's
                        # structure command reads its JMS from the models folder.
                        output_folder = ('models' if self.target_game == 'halo1'
                                         and folder == 'structure' else folder)
                        output_path = Path(
                            self.asset_path, output_folder,
                            name + ('.ass' if use_ass else '.jms'))
                    outputs.append((output_path, asset))
                if uses_jmi and jmi_children:
                    outputs.append((
                        Path(self.asset_path, self.asset_name + '.jmi'),
                        jmi_text(self.jms_version, jmi_children),
                    ))
            for index, animation in enumerate(animations):
                utils.update_job_count(process, '', geometry_count + index, preparation_count)
                if hasattr(animation, 'legacy_tracks'):
                    if self.target_game == 'halo1' and len(animation.name) >= 32:
                        self.warnings.append(f'{animation.name}: Halo 1 animation names must be shorter than 32 characters. Skipping animation')
                        self.skipped_legacy_animations.add(animation.name)
                        continue
                    try:
                        animation_text = self.jma_text(animation)
                    except ValueError as exc:
                        self.warnings.append(f'{exc}. Skipping animation')
                        self.skipped_legacy_animations.add(animation.name)
                        continue
                    outputs.append((Path(self.asset_path, 'animations', filename(animation.name.replace(':', ' ')) + self.animation_extension(animation)), animation_text))
                    if animation.suspension:
                        self.suspension_animations[animation.name.replace(' ', ':')] = animation
            utils.update_job_count(process, '', preparation_count, preparation_count)
        if self.external_animations:
            raise ExportCancelled('External GR2 animations cannot be exported by this game. Import their action tracks before exporting')
        if self.animation_composites:
            raise ExportCancelled('Composite animations are not supported by this game')
        if not outputs and single_animation:
            if self.skipped_legacy_animations:
                return False
            raise ExportCancelled('No JMS, ASS or JMA data matched the export selection')
        if len({str(path).casefold() for path, _ in outputs}) != len(outputs):
            raise ExportCancelled('Legacy output names collide; rename the affected BSP, permutation or animation')
        if self.shader_collections.dirty:
            outputs.append((self.shader_collections.path, self.shader_collections.text()))
        write_outputs(outputs, maya_order=self.export_settings.legacy_maya_order)
        if not single_animation:
            self.cleanup_intermediates(outputs)
        return True

    def cleanup_intermediates(self, outputs):
        root = Path(self.asset_path)
        expected = {path for path, _ in outputs}
        # Unsampled animations still belong to the asset during ACTIVE/NONE
        # exports. Include their current extension to remove obsolete variants.
        expected.update(root / 'animations' / (
            filename(animation.name.replace(':', ' ')) + self.animation_extension(animation))
            for animation in self.virtual_scene.animations
            if animation.name not in self.skipped_legacy_animations
            and (self.target_game != 'halo1' or len(animation.name) < 32))
        directories = {root / 'animations': ANIMATION_EXTENSIONS}
        # Geometry output batches are filtered before serialization. Only prune
        # folders for which this batch contains the complete inventory.
        if not self.limit_bsps_to_selection and not self.limit_perms_to_selection:
            roles = self.export_tag_types
            if 'render' in roles:
                directories[root / ('models' if self.target_game == 'halo1' else 'render')] = {'.jms', '.ass'}
            if self.target_game == 'halo1':
                if {'collision', 'physics'} <= roles:
                    directories[root / 'physics'] = {'.jms'}
            else:
                for role in ('collision', 'physics'):
                    if role in roles:
                        directories[root / role] = {'.jms', '.ass'}
            if {'structure', 'design'} <= roles:
                directories[root / 'structure'] = {'.jms', '.ass'}
                if self.target_game == 'halo1':
                    directories[root / 'models'] = {'.jms'}
            if (self.target_game == 'halo2' and 'render' in roles
                    and self.asset_type.name in {'PARTICLE_MODEL', 'DECORATOR_SET'}):
                directories[root] = {'.jmi'}
                # JMI children use one render folder per child, rather than the
                # asset's own render folder. Never descend into another asset.
                for child in root.iterdir():
                    if child.is_dir() and not child.is_symlink() and not any(child.glob('*.sidecar.xml')):
                        directories[child / 'render'] = {'.jms'}
        prune_intermediates(root, expected, directories)

    def _run_import_tool(self, tool_args, **kwargs):
        """Build patches for the executable this invocation actually selects."""
        if kwargs.get('force_tool') or self.target_game == 'halo1':
            tool_type = 'tool'
            kwargs['force_tool'] = True
        elif kwargs.get('force_tool_fast'):
            tool_type = 'tool_fast'
        else:
            tool_type = utils.get_tool_type()
        tool_path = Path(self.project_root, tool_type).with_suffix('.exe')
        kwargs['tool_patches'] = ToolPatcher(tool_path).import_patches(
            self.target_game,
            plane_builder=self.asset_type.name == 'SCENARIO',
        )
        return utils.run_tool(tool_args, **kwargs)

    def prepare_structure_seams(self, sources):
        """Rebuild current seams; return whether all BSPs need updating."""
        triangles = [triangle for source in sources for triangle in ass_seam_triangles(source)]
        self.structure_seams_present = bool(triangles)
        seams = Path(self.tags_dir, self.asset_path_relative,
                     self.asset_name).with_suffix('.structure_seams')
        if not triangles:
            print('--- Skipping structure seams: no seam faces', flush=True)
            scenario_path = seams.with_suffix('.scenario')
            if scenario_path.is_file():
                with ScenarioDocument(scenario_path, tags_root=self.tags_dir,
                                      game=self.target_game, must_exist=True) as scenario:
                    previous = scenario.reference(scenario.tag.root(), 'structure seams')
                    if (previous is not None and previous.RelativePathWithExtension.casefold() ==
                            str(utils.relative_path(seams)).replace('/', '\\').casefold()):
                        # The last seam was removed. Clear both BSP sides in
                        # this export; scenario postprocessing unlinks the tag.
                        return True
            return False
        previous = None
        if seams.is_file():
            try:
                with StructureSeamsDocument(seams, tags_root=self.tags_dir,
                                            game=self.target_game, must_exist=True) as tag:
                    previous = tag.compilation_signature()
            except Exception as error:
                print(f'--- Rebuilding unreadable structure seams: {error}', flush=True)
        print(f'--- Tool processing structure seams: {self.asset_path_relative}', flush=True)
        from ..legacy.seam_geometry import fresh_structure_seams, structure_seam_sources
        # Tool also uses surrounding BSP planes, so matching only the seam
        # faces cannot detect every change. An existing tag seeds its plane
        # solver and can retain different results for identical current input.
        with structure_seam_sources(sources), fresh_structure_seams(seams):
            self._run_import_tool(
                ['structure-seams', self.asset_path_relative],
                event_level=self.export_settings.event_level,
                force_tool=True,
            )
            if not seams.is_file():
                raise ExportCancelled(f'Seam compilation did not create the expected tag: {seams}')
            with StructureSeamsDocument(seams, tags_root=self.tags_dir,
                                        game=self.target_game, must_exist=True) as tag:
                if not any(seam.triangles for seam in tag.read_geometry()):
                    raise ExportCancelled(f'Seam compilation produced no seam geometry: {seams}')
                current = tag.compilation_signature()
        return previous != current

    def write_tags(self, single_animation=False):
        """Compile legacy model sources, then update object tags natively."""
        if self.asset_type.name == 'CINEMATIC':
            self.write_cinematic_graphs()
            return
        supported_asset_types = {'MODEL', 'SKY', 'ANIMATION', 'SINGLE_ANIMATION', 'SCENARIO', 'CAMERA_TRACK_SET', 'MULTI_MODEL'}
        if self.target_game in {'halo2', 'halo3', 'halo3odst'}:
            supported_asset_types.update({'PARTICLE_MODEL', 'DECORATOR_SET'})
            if self.target_game in {'halo3', 'halo3odst'}:
                supported_asset_types.add('CINEMATIC')
        if self.asset_type.name not in supported_asset_types:
            raise ExportCancelled(
                f'Legacy tag writing is not implemented for {self.asset_type.name.lower()} assets')

        print("\n\nWriting Tags")
        print("-----------------------------------------------------------------------\n")
        animation_only = single_animation or self.asset_type.name in {
            'ANIMATION', 'SINGLE_ANIMATION'}
        halo1_tool_options = {}
        if self.target_game == 'halo1':
            # H1 has no usable tool_fast equivalent for these imports.
            halo1_tool_options = {'force_tool': True}
            self.copy_halo1_templates(animation_only)
        elif self.target_game in {'halo2', 'halo3', 'halo3odst'}:
            self.copy_classic_model_templates(animation_only)
        if self.asset_type.name == 'SCENARIO':
            structure_dir = Path(
                self.asset_path, 'models' if self.target_game == 'halo1' else 'structure')
            structure_extension = '.jms' if self.target_game == 'halo1' else '.ass'
            sources = sorted(
                path for path in structure_dir.iterdir()
                if path.is_file() and path.suffix.lower() == structure_extension
            ) if structure_dir.is_dir() else []
            structure_sources, design_sources = [], {}
            for source in sources:
                bsp, is_design = self.structure_source_assignment(source)
                if self.limit_bsps_to_selection and bsp not in self.selected_bsps:
                    continue
                role = 'design' if is_design else 'structure'
                if role not in self.export_tag_types:
                    continue
                if is_design:
                    design_sources[source] = bsp
                else:
                    structure_sources.append(source)
            if not structure_sources and not design_sources:
                if self.limit_bsps_to_selection:
                    raise ExportCancelled(
                        f'No selected BSP {structure_extension} sources were found in {structure_dir}')
                raise ExportCancelled(
                    f'No {structure_extension} structure sources were found in {structure_dir}')
            if self.target_game == 'halo1':
                self.update_halo1_material_emissives()
            def compile_source(source):
                is_design = source in design_sources
                print(f'--- Tool processing {"design" if is_design else "BSP"}: {source.stem} ({source})', flush=True)
                error_path = source.with_name(source.stem + '_errors.wrl')
                previous = error_path.stat() if error_path.is_file() else None
                if self.target_game == 'halo1':
                    command = ['structure', self.asset_path_relative, source.stem]
                else:
                    command = [
                        ('structure-new-from-ass' if self.target_game == 'halo2'
                         else 'structure-design' if is_design else 'structure'),
                        source.relative_to(self.data_dir),
                    ]
                if self.target_game == 'halo1' and self.export_settings.halo1_fix_phantom_bsp:
                    command.append('true')
                tool_failed = False
                try:
                    shaders = (self.ensure_halo1_shaders([source], 'shader_environment')
                               if self.target_game == 'halo1' else nullcontext({}))
                    with shaders as expected:
                        self._run_import_tool(
                            command,
                            event_level=self.export_settings.event_level,
                            force_tool=True,
                        )
                        if self.target_game == 'halo1':
                            destination = Path(self.tags_dir, self.asset_path_relative,
                                               source.stem).with_suffix('.scenario_structure_bsp')
                            self.repair_halo1_shader_paths(destination, expected)
                        elif self.target_game == 'halo2':
                            destination = Path(self.tags_dir, self.asset_path_relative,
                                               source.stem).with_suffix('.scenario_structure_bsp')
                            # Tool retains authored water definitions when the
                            # last +media plane is removed. Sync absence too,
                            # only after successfully compiling this BSP.
                            write_water_definition(destination, self.tags_dir,
                                                   self.halo2_water_settings.get(source.stem))
                except subprocess.CalledProcessError:
                    tool_failed = True
                    raise
                finally:
                    # Scene restoration has already finished before write_tags.
                    # Only display diagnostics produced by this Tool invocation.
                    try:
                        current = error_path.stat() if error_path.is_file() else None
                        if (tool_failed or self.export_settings.import_wrl) and current and (previous is None or
                                (current.st_mtime_ns, current.st_size) !=
                                (previous.st_mtime_ns, previous.st_size)):
                            from ..legacy.wrl import import_errors
                            import_errors(error_path, self.context.scene,
                                          self.rotation_correction, self.to_halo_scale)
                    except Exception as error:
                        print(f'Could not import BSP error geometry: {error}')
                if self.target_game in {'halo3', 'halo3odst'}:
                    destination = Path(self.tags_dir, self.asset_path_relative, source.stem).with_suffix(
                        '.structure_design' if is_design else '.scenario_structure_bsp')
                    if not destination.is_file():
                        raise ExportCancelled(
                            f'Structure compilation did not create the expected tag: {destination}')
                    if is_design:
                        properties = {}
                        for ob, (props, region, _, _) in getattr(self, 'ob_halo_data', {}).items():
                            if region != design_sources[source] or props.get('bungie_mesh_type') != 18:
                                continue
                            direction = props.get('foundry_water_direction', (0., 0., 0.))
                            if self.mirror:
                                direction = (direction[0], -direction[1], direction[2])
                            name = legacy_instance_name(ob.name, props, 18, self.target_game)[1:]
                            properties[name] = (direction, props.get('foundry_water_angle', 0.))
                        if properties:
                            with StructureDesignDocument(destination, tags_root=self.tags_dir,
                                                         game=self.target_game, must_exist=True) as design:
                                design.set_water_properties(properties)
            if self.target_game in {'halo3', 'halo3odst'} and structure_sources:
                # Seams are a level-wide input, including BSPs outside a
                # selected export. Tool reads ASS directly, before any BSPs.
                level_sources = [source for source in sources
                                 if not self.structure_source_assignment(source)[1]]
                if self.prepare_structure_seams(level_sources):
                    # A changed shared seam can invalidate the other side's
                    # indices too. Compile the level once using the new tag.
                    if set(level_sources) != set(structure_sources):
                        print('--- Seam changes require rebuilding the other BSPs in this level', flush=True)
                    structure_sources = level_sources
            for source in [*structure_sources, *design_sources]:
                compile_source(source)
            self.write_classic_scenario_tag(structure_sources, design_sources)
            return
        if self.asset_type.name in {'PARTICLE_MODEL', 'DECORATOR_SET'}:
            source = Path(self.asset_path, self.asset_name + '.jmi')
            if not source.is_file():
                raise ExportCancelled(
                    f'No JMI source was found for {self.asset_type.name.lower()}: '
                    f'{source}')
            command = ('import-particle-model' if self.asset_type.name == 'PARTICLE_MODEL'
                       else 'import-decorator-set')
            self._run_import_tool(
                [command, str(Path(self.asset_path_relative,
                                   self.asset_name + '.jmi'))],
                event_level=self.export_settings.event_level,
            )
            destination = Path(
                self.tags_dir, self.asset_path_relative, self.asset_name
            ).with_suffix(
                '.particle_model' if self.asset_type.name == 'PARTICLE_MODEL'
                else '.decorator_set')
            if not destination.is_file():
                raise ExportCancelled(
                    f'{command} did not create the expected tag: {destination}')
            print(f'--- Wrote {destination}')
            return
        if not animation_only:
            if self.target_game == 'halo1':
                models = Path(self.asset_path, 'models')
                physics = Path(self.asset_path, 'physics')
                model_sources = sorted(models.glob('*.jms')) if models.is_dir() else []
                if model_sources:
                    with self.ensure_halo1_shaders(model_sources, 'shader_model') as expected:
                        self._run_import_tool(['model', self.asset_path_relative],
                                       event_level=self.export_settings.event_level,
                                       **halo1_tool_options)
                        base = Path(self.tags_dir, self.asset_path_relative, self.asset_name)
                        destinations = [base.with_suffix(extension) for extension in ('.gbxmodel', '.model')
                                        if base.with_suffix(extension).is_file()]
                        if not destinations:
                            raise ExportCancelled(f'Model compilation did not create the expected tag: {base}')
                        for destination in destinations:
                            self.repair_halo1_shader_paths(destination, expected)
                if physics.is_dir() and any(physics.glob('*.jms')):
                    # Collision triangles and physics mass points share the
                    # same source folder in H1, but need separate imports.
                    mesh_types = {data[0].get('bungie_mesh_type')
                                  for data in self.ob_halo_data.values()}
                    for role, mesh_type, command in (
                            ('collision', 2, 'collision-geometry'),
                            ('physics', 12, 'physics')):
                        if role not in self.export_tag_types or mesh_type not in mesh_types:
                            continue
                        self._run_import_tool([command, self.asset_path_relative],
                                       event_level=self.export_settings.event_level,
                                       **halo1_tool_options)
            else:
                sources = {}
                for role in ('render', 'collision', 'physics'):
                    directory = Path(self.asset_path, role)
                    sources[role] = directory.is_dir() and any(
                        path.is_file() and path.suffix.lower() in {'.jms', '.ass'}
                        for path in directory.iterdir())
                if all(sources.values()):
                    command = ('bulk-import-model-folder'
                               if self.target_game == 'halo2' or self.export_settings.lightmap_structure
                               else 'bulk-import-model-folder-draft')
                    self._run_import_tool([command, self.asset_path_relative],
                                   event_level=self.export_settings.event_level)
                else:
                    # Bulk import attempts all three components even when a
                    # source folder is empty or absent, producing Tool errors.
                    for role, present in sources.items():
                        if not present:
                            continue
                        command = [role, self.asset_path_relative]
                        if role == 'render' and self.target_game in {'halo3', 'halo3odst'}:
                            command.append('final' if self.export_settings.lightmap_structure else 'draft')
                        self._run_import_tool(command, event_level=self.export_settings.event_level)
                    # Individual imports only create component tags; bulk
                    # import would also create and link the parent model tag.
                    model_path = Path(self.tags_dir, self.asset_path_relative,
                                      self.asset_name).with_suffix('.model')
                    with ModelTag(path=model_path) as model:
                        model.set_asset_paths()

        animation_dir = Path(self.asset_path, 'animations')
        has_animation_sources = (animation_dir.is_dir() and any(
            path.is_file() and path.suffix.lower().startswith('.jm')
            for path in animation_dir.iterdir()))
        import_animations = (single_animation or self.has_blend_animations()) and has_animation_sources
        graph_extension = ('model_animations' if self.target_game == 'halo1'
                           else 'model_animation_graph')
        graph_path = Path(self.tags_dir, self.asset_path_relative,
                          self.asset_name).with_suffix('.' + graph_extension)
        if import_animations:
            self.write_animation_compression(graph_path, single_animation)
            command = 'animations' if self.target_game == 'halo1' else 'model-animations'
            animation_tool_options = dict(halo1_tool_options)
            if self.target_game == 'halo1':
                # H1 asks whether to save the graph after animations have been
                # removed. The output viewer has no interactive stdin.
                animation_tool_options['input_data'] = b'y\n'
            self._run_import_tool([command, self.asset_path_relative],
                           event_level=self.export_settings.event_level,
                           **animation_tool_options)
            # New animations only acquire tag entries on the first import.
            # Compile again if their requested compression differs from Tool's default.
            if self.write_animation_compression(graph_path, single_animation):
                self._run_import_tool([command, self.asset_path_relative],
                               event_level=self.export_settings.event_level,
                               **animation_tool_options)
        elif self.target_game == 'halo1' and graph_path.is_file():
            self.write_animation_compression(graph_path, single_animation)
        if import_animations or (self.scene_settings.blend_screens_from_blender
                                 and graph_path.is_file()):
            self.write_classic_animation_events()
        if self.target_game == 'halo1' and import_animations:
            self.write_vehicle_suspension(graph_path)
            self.validate_halo1_animation_skeleton()
        if self.asset_type.name in {'MODEL', 'SKY'}:
            self.write_object_tags()

    def write_animation_compression(self, graph_path: Path, single_animation=False) -> bool:
        if self.target_game != 'halo1' and not graph_path.is_file():
            return False
        with AnimationGraphTag(graph_path, tag_must_exist=False) as graph:
            if self.target_game == 'halo1':
                graph.set_halo1_compression(self.scene_settings.compress_all_animations,
                                           self.scene_settings.force_idle_compression)
            else:
                if single_animation:
                    animations = [SimpleNamespace(name=Path(bpy.data.filepath).stem,
                                                  compression='Medium')]
                else:
                    animations = list(self.scene_settings.animations)
                    if self.export_settings.export_animations == 'ACTIVE':
                        index = self.scene_settings.active_animation_index
                        animations = animations[index:index + 1] if index >= 0 else []
                    animations = [animation for animation in animations
                                  if animation.export_this
                                  and animation.name not in self.skipped_legacy_animations]
                graph.set_compression(animations, self.scene_settings.forced_animation_compression)
            return graph.tag_has_changes

    def has_blend_animations(self):
        """Disk intermediates alone must never opt an asset into animation import."""
        if self.export_settings.export_animations == 'NONE':
            return False
        animations = self.scene_settings.animations
        if self.export_settings.export_animations == 'ACTIVE':
            index = self.scene_settings.active_animation_index
            return (0 <= index < len(animations) and animations[index].export_this
                    and animations[index].name not in self.skipped_legacy_animations
                    and (self.target_game != 'halo1' or len(animations[index].name) < 32))
        return any(animation.export_this and animation.name not in self.skipped_legacy_animations
                   and (self.target_game != 'halo1' or len(animation.name) < 32)
                   for animation in animations)

    def validate_halo1_animation_skeleton(self):
        """Never silently accept a template graph with incompatible node indices."""
        base = Path(self.tags_dir, self.asset_path_relative, self.asset_name)
        model_path = base.with_suffix('.gbxmodel')
        animation_path = base.with_suffix('.model_animations')
        if not model_path.is_file() or not animation_path.is_file():
            return
        with TagDocument(model_path, tags_root=self.tags_dir, game='halo1', must_exist=True) as model, \
                TagDocument(animation_path, tags_root=self.tags_dir, game='halo1', must_exist=True) as graph:
            def skeleton(doc):
                return [tuple(doc.value(node, field) for field in (
                    'name', 'first child node', 'next sibling node'))
                    for node in doc.block(doc.tag.root(), 'nodes')]
            if skeleton(model) != skeleton(graph):
                raise ExportCancelled(
                    'H1 model and animation node order differs. Export geometry and '
                    'all animations together with the same sorting settings; '
                    'rebuild intermediate files before using Tags Only.')
            checksum = model.value(model.tag.root(), 'node list checksum')
            count = len(model.block(model.tag.root(), 'nodes'))
            for animation in graph.block(graph.tag.root(), 'animations'):
                if (graph.value(animation, 'node list checksum') != checksum or
                        graph.value(animation, 'node count') != count):
                    raise ExportCancelled(
                        f'H1 animation {graph.value(animation, "name")!r} has an '
                        'incompatible skeleton. Export all animations and geometry together.')

    def copy_classic_model_templates(self, animation_only=False):
        """Seed missing H2/H3/ODST model tags before Tool imports them."""
        if self.asset_type.name not in {'MODEL', 'SKY', 'ANIMATION', 'SINGLE_ANIMATION'}:
            return
        templates = [('template_model_animation_graph', 'model_animation_graph')]
        if not animation_only and self.asset_type.name in {'MODEL', 'SKY'}:
            templates.extend((
                ('template_model', 'model'),
                ('template_render_model', 'render_model'),
                ('template_collision_model', 'collision_model'),
                ('template_physics_model', 'physics_model'),
            ))
        base = Path(self.tags_dir, self.asset_path_relative, self.asset_name)
        copies = []
        for setting, extension in templates:
            template = getattr(self.scene_settings, setting, '').strip()
            if not template:
                continue
            source = Path(self.tags_dir, utils.relative_path(template))
            destination = base.with_suffix('.' + extension)
            if destination.is_file():
                continue
            if not source.is_file():
                utils.print_warning(f'Tag template does not exist: {source}')
                continue
            copies.append((source, destination))
        for source, destination in copies:
            destination.parent.mkdir(parents=True, exist_ok=True)
            utils.copy_file(source, destination)
            print(f'--- Loaded template {destination}')

    def copy_halo1_templates(self, animation_only=False):
        """Seed H1 tags before Tool imports; explicit component templates win."""
        templates = {}
        component_fields = {
            'model': 'gbxmodel',
            'animation graph': 'model_animations',
            'collision model': 'model_collision_geometry',
            'physics': 'physics',
        }
        if self.asset_type.name in {'MODEL', 'ANIMATION', 'SINGLE_ANIMATION', 'SCENARIO'}:
            outputs = {'scenario'} if self.asset_type.name == 'SCENARIO' else {
                kind for kind in self.supported_object_tag_types
                if getattr(self.scene_settings, 'output_' + kind, False)
            }
            for kind in sorted(outputs):
                template = getattr(self.scene_settings, 'template_' + kind, '').strip()
                if not template:
                    continue
                source = Path(self.tags_dir, utils.relative_path(template))
                if not source.is_file():
                    utils.print_warning(f'Tag template does not exist: {source}')
                    continue
                if not animation_only:
                    templates[kind] = source
                if kind != 'scenario':
                    with TagDocument(source, tags_root=self.tags_dir, game='halo1',
                                     must_exist=True) as tag:
                        for field, extension in component_fields.items():
                            ref = tag.reference(tag.tag.root(), field)
                            if ref and (not animation_only or extension == 'model_animations'):
                                templates.setdefault(extension, Path(ref.Filename))

        for setting, extension in (
            ('template_render_model', 'gbxmodel'),
            ('template_collision_model', 'model_collision_geometry'),
            ('template_physics_model', 'physics'),
            ('template_model_animation_graph', 'model_animations'),
        ):
            if animation_only and extension != 'model_animations':
                continue
            template = getattr(self.scene_settings, setting, '').strip()
            if template:
                templates[extension] = Path(self.tags_dir, utils.relative_path(template))

        # Validate and read the complete batch before replacing destinations.
        # Reading first also handles templates that are another output's source.
        copies = []
        base = Path(self.tags_dir, self.asset_path_relative, self.asset_name)
        for extension, source in templates.items():
            destination = base.with_suffix('.' + extension)
            if (extension == 'model_animations' and destination.is_file()
                    and (not self.has_blend_animations()
                         or not any(Path(self.asset_path, 'animations').glob('*.jm*')))):
                # Tool will not rebuild this graph. Keep its compiled skeleton
                # instead of replacing it with the template's old indices.
                continue
            if not source.is_file():
                utils.print_warning(f'Tag template does not exist: {source}')
                continue
            if source.resolve() != destination.resolve():
                copies.append((destination, source.read_bytes()))
        for destination, data in copies:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile(dir=destination.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(data)
            try:
                temporary.replace(destination)
            finally:
                temporary.unlink(missing_ok=True)
            print(f'--- Loaded template {destination}')

    def prepare_halo2_water(self):
        """Resolve the single water definition allowed in each exported H2 BSP."""
        self.halo2_water_settings = {}
        if self.asset_type.name != 'SCENARIO' or 'structure' not in self.export_tag_types:
            return
        owners = {}
        water_objects = defaultdict(list)
        for ob, (props, region, permutation, _) in self.ob_halo_data.items():
            if props.get('bungie_mesh_type') != 17:
                continue
            if self.limit_bsps_to_selection and region not in self.selected_bsps:
                continue
            if self.limit_perms_to_selection and permutation not in self.selected_permutations:
                continue
            settings = water_settings(ob.nwo)
            shader = settings['shader'].strip()
            settings['shader'] = utils.relative_path(shader) if shader else ''
            if settings['shader'] and Path(settings['shader']).suffix.lower() != '.shader':
                raise ExportCancelled(f'{ob.name}: Halo 2 water requires a .shader tag')
            previous = self.halo2_water_settings.get(region)
            if previous is not None and previous != settings:
                raise ExportCancelled(
                    f'BSP [{region}] has conflicting water settings on [{owners[region]}] '
                    f'and [{ob.name}]. Halo 2 supports one water definition per BSP; '
                    'use matching water settings on these objects.')
            self.halo2_water_settings[region] = settings
            owners[region] = ob.name
            water_objects[region].append(ob)
        for region, objects in water_objects.items():
            try:
                self.halo2_water_settings[region]['height'] = water_plane_height(
                    objects, self.halo_transform_scale, self.depsgraph)
            except ValueError as error:
                raise ExportCancelled(f'BSP [{region}]: {error}') from error

    def prepare_halo2_material_emissives(self, allow_localize=True, write_values=True):
        """Resolve asset shader paths before ASS allocates shader collections."""
        folder = asset_shader_folder(self.scene_settings.sidecar_path, self.data_dir, self.tags_dir)
        requested = {}
        for ob in self.ob_halo_data:
            for slot in getattr(ob, 'material_slots', ()):
                material = slot.material
                if material is None:
                    continue
                prop = next((p for p in material.nwo.material_props if p.type == 'emissive'), None)
                if prop is None:
                    continue
                source = shader_environment_path(utils.relative_path(material.nwo.shader_path), self.tags_dir, 'halo2')
                values = (float(prop.material_lighting_emissive_power), tuple(prop.material_lighting_emissive_color))
                if source in requested and requested[source][0] != values:
                    raise ExportCancelled(f'Materials sharing {source} have conflicting emissive power or color')
                requested.setdefault(source, (values, set()))[1].add(material)
        for source, ((power, color), materials) in requested.items():
            if source.parent != folder and not allow_localize:
                raise ExportCancelled('Run a full export to localize Halo 2 emissive shaders and update ASS references')
            target, _ = localize_shader_environment(source, folder, self.tags_dir, 'halo2')
            path = str(target.relative_to(Path(self.tags_dir).resolve()))
            if write_values:
                write_material_emissive(path, self.tags_dir, power, color, 'halo2')
            for material in materials:
                material.nwo.shader_path = path

    def prepare_halo1_material_shaders(self, shader_type):
        """Convert environment tags only for non-scenario geometry exports."""
        if shader_type != 'shader_model':
            return {}
        conversions = getattr(self, 'halo1_shader_conversions', {})
        self.halo1_shader_conversions = conversions
        for ob in self.ob_halo_data:
            for slot in getattr(ob, 'material_slots', ()):
                material = slot.material
                if material is None:
                    continue
                path = utils.relative_path(material.nwo.shader_path.strip())
                source = Path(path)
                if (source.suffix.lower() != '.shader_environment'
                        or not (Path(self.tags_dir) / source).is_file()):
                    continue
                if source not in conversions:
                    try:
                        conversions[source] = convert_shader(source, self.tags_dir, '.' + shader_type)
                    except (OSError, RuntimeError, ValueError) as error:
                        raise ExportCancelled(f'{material.name}: could not convert shader: {error}') from error
                    print(f'--- Converted {source} to {conversions[source]}')
                material.nwo.shader_path = str(conversions[source])
        return conversions

    def update_halo1_material_emissives(self) -> None:
        """Apply material emission to the selected shader paths."""
        requested = {}
        for ob in self.ob_halo_data:
            for slot in getattr(ob, 'material_slots', ()):
                material = slot.material
                if material is None:
                    continue
                prop = next((item for item in material.nwo.material_props
                             if item.type == 'emissive'), None)
                if prop is None:
                    continue
                if not material.nwo.shader_path.strip():
                    continue
                tag_path = utils.relative_path(material.nwo.shader_path)
                shader_path = shader_environment_path(tag_path, self.tags_dir, 'halo1')
                key = str(shader_path).casefold()
                values = (float(prop.material_lighting_emissive_power),
                          tuple(float(channel) for channel in prop.material_lighting_emissive_color[:3]))
                previous = requested.get(key)
                if previous is not None and previous[1] != values:
                    raise ExportCancelled(
                        f'{material.name}: materials sharing {tag_path} have conflicting emissive values')
                requested[key] = (tag_path, values)

        for tag_path, (power, color) in requested.values():
            if write_material_emissive(tag_path, self.tags_dir, power, color):
                print(f'--- Updated emissive shader {tag_path}')

    def ensure_halo1_shaders(self, source_paths: list[Path], shader_type: str):
        """Resolve JMS names to selected paths, providing temporary Tool aliases."""
        if self.target_game != 'halo1':
            return nullcontext({})
        conversions = self.prepare_halo1_material_shaders(shader_type)
        ensure_invalid_shader(self.tags_dir)
        if conversions or not self.shader_collections.halo1_names_reserved:
            self.shader_collections.reserve_halo1_paths(
                [str(INVALID_SHADER_PATH), *map(str, conversions), *map(str, conversions.values()),
                 *map(str, getattr(self, 'halo1_shader_paths', {}).values()),
                 *(slot.material.nwo.shader_path for ob in self.ob_halo_data
                 for slot in getattr(ob, 'material_slots', ()) if slot.material is not None)])
        candidates = defaultdict(set)
        for name, path in getattr(self, 'halo1_shader_paths', {}).items():
            candidates[name].add(conversions.get(Path(path), path))
        # Tags Only can compile JMS written before the material was converted.
        for original, converted in conversions.items():
            candidates[self.shader_collections.material_name(str(original)).casefold()].add(converted)
            candidates[halo1_shader_lookup(original.stem, model=shader_type == 'shader_model')].add(converted)
        for ob in self.ob_halo_data:
            for slot in getattr(ob, 'material_slots', ()):
                material = slot.material
                if material is None:
                    continue
                path = material.nwo.shader_path.strip()
                try:
                    target = shader_environment_path(utils.relative_path(path), self.tags_dir) if path else None
                except (OSError, ValueError):
                    target = None
                wanted = (target.relative_to(Path(self.tags_dir).resolve())
                          if target is not None else INVALID_SHADER_PATH)
                name = self.shader_collections.material_name(path) if target is not None else 'invalid'
                candidates[name.casefold()].add(wanted)
                # Tags Only may use JMS from before full-path aliases existed.
                old_name = (target.stem if target is not None else
                            material.name)
                old_key = halo1_shader_lookup(old_name, model=shader_type == 'shader_model')
                candidates[old_key].add(wanted)
        expected = {}
        for source in source_paths:
            asset = jms.JMS.from_file(source)
            rewritten = False
            for material in asset.materials:
                name = halo1_shader_lookup(material.name, model=shader_type == 'shader_model')
                if name.startswith('+'):
                    continue
                paths = candidates.get(name, {INVALID_SHADER_PATH})
                if len(paths) != 1:
                    raise ExportCancelled(
                        f'{source.name}: shader name {material.name!r} has multiple selected paths. '
                        'Run a full export to distinguish these shaders in JMS')
                wanted = next(iter(paths))
                original_name = name
                if wanted in conversions.values():
                    # Persist converted names so the next Tags Only export can
                    # resolve them after this export's conversion cache is gone.
                    name = self.shader_collections.material_name(str(wanted)).casefold()
                    flags = (material.name[len(material.name.rstrip('%#!@*$^-&')):]
                             if shader_type == 'shader_environment' else '')
                    replacement = name + flags
                    if material.name != replacement:
                        material.name = replacement
                        rewritten = True
                if wanted == INVALID_SHADER_PATH:
                    flags = (material.name[len(material.name.rstrip('%#!@*$^-&')):]
                             if shader_type == 'shader_environment' else '')
                    replacement = 'invalid' + flags
                    if material.name != replacement:
                        material.name = replacement
                        rewritten = True
                    name = 'invalid'
                filename(name + Path(wanted).suffix)
                previous = expected.get(name)
                if previous is not None and previous != wanted:
                    raise ExportCancelled(f'{source.name}: conflicting shader paths for {name}')
                expected[name] = wanted
                # Model JMS has no face-side flags; update the selected shader.
                if (shader_type == 'shader_model' and Path(wanted).suffix.lower() == '.shader_model'
                        and (name in self.halo1_two_sided_shaders or original_name in self.halo1_two_sided_shaders)):
                    with TagDocument(wanted, tags_root=self.tags_dir, game='halo1', must_exist=True) as shader:
                        properties = shader.required_field(shader.tag.root(), 'properties').as_struct()
                        flags = shader.required_field(properties, 'flags')
                        if not flags.get_flag('two sided'):
                            flags.set_flag('two sided', True)
                            shader.tag_has_changes = True
            if rewritten:
                with source.open('w', encoding='utf-8') as stream:
                    write_jms(asset, stream)
        return shader_import_paths(self.tags_dir, expected)

    def repair_halo1_shader_paths(self, destination, expected):
        try:
            changed = repair_shader_references(destination, self.tags_dir, expected)
        except (OSError, ValueError) as error:
            raise ExportCancelled(str(error)) from error
        # if changed:
        #     print(f'--- Corrected {changed} shader reference(s) in {destination}')

    def halo1_object_references(self, base, object_template=''):
        """Resolve components from the asset, never from stale output files alone."""
        mesh_types = {data[0].get('bungie_mesh_type') for data in self.ob_halo_data.values()}
        present = {
            'model': bool(mesh_types.intersection({3, 11})),
            'collision model': 2 in mesh_types,
            'physics': 12 in mesh_types,
            'animation graph': any(a.export_this for a in self.scene_settings.animations),
        }
        inherited = {}
        if object_template:
            source = Path(self.tags_dir, utils.relative_path(object_template))
            with TagDocument(source, tags_root=self.tags_dir, game='halo1', must_exist=True) as tag:
                for field in present:
                    reference = tag.reference(tag.tag.root(), field)
                    if reference:
                        inherited[field] = reference.RelativePathWithExtension
        result = {}
        for field, setting, extension in (
            ('model', 'template_render_model', 'gbxmodel'),
            ('collision model', 'template_collision_model', 'model_collision_geometry'),
            ('animation graph', 'template_model_animation_graph', 'model_animations'),
            ('physics', 'template_physics_model', 'physics'),
        ):
            template = getattr(self.scene_settings, setting, '').strip()
            template_exists = bool(template and Path(
                self.tags_dir, utils.relative_path(template)).is_file())
            if present[field] or template_exists:
                destination = base.with_suffix('.' + extension)
                if not destination.is_file():
                    raise ExportCancelled(f'Asset component tag does not exist: {destination}')
                result[field] = utils.relative_path(destination)
            else:
                result[field] = inherited.get(field)
        return result

    def write_object_tags(self):
        """Create selected high-level object tags through blam-tags."""
        model_path = Path(self.tags_dir, self.asset_path_relative,
                          self.asset_name).with_suffix(
                              '.gbxmodel' if self.target_game == 'halo1' else '.model')
        if (self.asset_type.name == 'SKY'
                and self.target_game in {'halo1', 'halo2'}):
            self.write_classic_sky_tag(model_path)
            return
        if self.target_game != 'halo1' and not model_path.is_file():
            raise ExportCancelled(
                f'Model compilation did not create the expected tag: {model_path}')

        if self.target_game in {'halo2', 'halo3', 'halo3odst'}:
            # A local component file can be left by an earlier export or by a
            # model template. Only Blender content or an explicit component
            # template makes its reference valid for this asset.
            mesh_types = {data[0].get('bungie_mesh_type')
                          for data in self.ob_halo_data.values()}
            authored_components = {
                'render_model': bool(mesh_types.intersection({3, 11})),
                'collision_model': 2 in mesh_types,
                'model_animation_graph': any(animation.export_this
                                             for animation in self.scene_settings.animations),
                'physics_model': 12 in mesh_types,
            }
            allowed_components = {
                extension for extension, authored in authored_components.items()
                if authored or (template := getattr(
                    self.scene_settings, 'template_' + extension, '').strip())
                and Path(self.tags_dir, utils.relative_path(template)).is_file()
            }
            with ModelTag(path=model_path) as model:
                model.set_asset_paths(allowed_components=allowed_components)
            print(f'--- Wrote model tag paths to {model_path}')

        outputs = {'scenery'} if self.asset_type.name == 'SKY' else {
            tag_type for tag_type in self.supported_object_tag_types
            if getattr(self.scene_settings, 'output_' + tag_type, False)
        }
        model_reference = utils.relative_path(model_path)
        for tag_type in sorted(outputs):
            destination = model_path.with_suffix('.' + tag_type)
            template = getattr(self.scene_settings, 'template_' + tag_type, '')
            if template:
                template_path = Path(self.tags_dir, utils.relative_path(template))
                if not template_path.is_file():
                    utils.print_warning(
                        f'Tag template does not exist: {template_path}')
                    template = ''
                elif not destination.exists():
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    utils.copy_file(template_path, destination)
                    print(f'--- Loaded {tag_type} tag template')

            with ObjectDocument(destination, tags_root=self.tags_dir,
                                game=self.target_game) as tag:
                if self.target_game == 'halo1':
                    base = model_path.with_suffix('')
                    references = self.halo1_object_references(base, template)
                    for field, path in references.items():
                        tag.set_reference(tag.object_struct(), field, path)
                else:
                    tag.set_model_tag_path(model_reference)
            print(f'--- Wrote {destination}')

    def structure_source_assignment(self, source: Path) -> tuple[str, bool]:
        """Recover the BSP/role encoded from Foundry's region assignment."""
        if self.target_game not in {'halo3', 'halo3odst'}:
            return source.stem, False
        matches = set()
        for region in self.scene_settings.regions_table:
            if source.stem == region.name:
                matches.add((region.name, False))
            if source.stem == region.name + '_design':
                matches.add((region.name, True))
        if len(matches) > 1:
            raise ExportCancelled(
                f'Ambiguous structure source {source.name}: BSP names collide with design output names')
        if matches:
            return matches.pop()
        # Tags Only can reuse intermediates whose BSP is no longer in the scene.
        if source.stem.endswith('_design'):
            return source.stem[:-7], True
        return source.stem, False

    def write_classic_scenario_tag(self, structure_sources: list[Path],
                                   design_sources: dict[Path, str] | None = None) -> None:
        """Create/update a classic scenario with its compiled BSP references."""
        destination = Path(
            self.tags_dir, self.asset_path_relative, self.asset_name
        ).with_suffix('.scenario')
        is_new = not destination.is_file()
        bsp_paths: list[Path] = []
        for source in structure_sources:
            bsp = Path(
                self.tags_dir, self.asset_path_relative, source.stem
            ).with_suffix('.scenario_structure_bsp')
            if not bsp.is_file():
                raise ExportCancelled(
                    f'Structure compilation did not create the expected tag: {bsp}')
            bsp_paths.append(Path(utils.relative_path(bsp)))

        design_paths = {}
        for source, bsp_name in (design_sources or {}).items():
            bsp = Path(self.tags_dir, self.asset_path_relative,
                       bsp_name).with_suffix('.scenario_structure_bsp')
            design = Path(self.tags_dir, self.asset_path_relative,
                          source.stem).with_suffix('.structure_design')
            for tag in (bsp, design):
                if not tag.is_file():
                    raise ExportCancelled(f'Structure compilation did not create the expected tag: {tag}')
            bsp_reference = Path(utils.relative_path(bsp))
            design_paths[bsp_reference] = Path(utils.relative_path(design))
            if bsp_reference not in bsp_paths:
                bsp_paths.append(bsp_reference)

        with ScenarioDocument(
            destination, tags_root=self.tags_dir, game=self.target_game
        ) as scenario:
            scenario.ensure_structure_bsps(bsp_paths)
            if (structure_sources and 'structure' in self.export_tag_types
                    and not self.limit_bsps_to_selection and not self.export_settings.preserve_non_asset_bsps):
                scenario.retain_structure_bsps(bsp_paths)
            if design_paths:
                scenario.set_structure_designs(design_paths)
            if self.target_game in {'halo3', 'halo3odst'} and structure_sources:
                seams = destination.with_suffix('.structure_seams')
                if seams.is_file() and getattr(self, 'structure_seams_present', True):
                    scenario.set_reference(scenario.tag.root(), 'structure seams',
                                           utils.relative_path(seams))
                else:
                    previous = scenario.reference(scenario.tag.root(), 'structure seams')
                    if (previous is not None and previous.RelativePathWithExtension.casefold() ==
                            str(utils.relative_path(seams)).replace('/', '\\').casefold()):
                        scenario.set_reference(scenario.tag.root(), 'structure seams', None)
            if is_new:
                scenario.create_default_profile()
                scenario.set_scenario_type(self.scene_settings.scenario_type)
        print(f'--- Wrote {destination}')

    def write_classic_sky_tag(self, model_path: Path) -> None:
        """Create/update the distinct H1/H2 sky tag reference layout."""
        destination = model_path.with_suffix('.sky')
        suns = [ob for ob in self.sky_lights if ob.data.type == 'SUN']
        if len(suns) > MAX_SKY_LIGHTS:
            raise ExportCancelled(
                f'Sky tags support at most {MAX_SKY_LIGHTS} sun lights; found {len(suns)}')
        with SkyDocument(destination, tags_root=self.tags_dir,
                         game=self.target_game) as tag:
            root = tag.tag.root()
            if self.target_game == 'halo1':
                tag.set_reference(root, 'model', utils.relative_path(model_path))
                animation = model_path.with_suffix('.model_animations')
            else:
                render_model = model_path.with_suffix('.render_model')
                if not render_model.is_file():
                    raise ExportCancelled(
                        f'Sky compilation did not create the expected tag: {render_model}')
                tag.set_reference(root, 'render model',
                                  utils.relative_path(render_model))
                if tag.tag_is_new:
                    tag.required_field(root, 'render model scale').set(1.0)
                    tag.required_field(root, 'movement scale').set(1.0)
                animation = model_path.with_suffix('.model_animation_graph')
            if animation.is_file():
                tag.set_reference(root, 'animation graph',
                                  utils.relative_path(animation))
            # An empty Blender light list means the tag lights are authored by hand.
            if suns:
                rotation = Matrix.Rotation(
                    utils.blender_halo_rotation_diff(self.scene_settings.forward_direction),
                    3, 'Z')
                records = []
                for ob in suns:
                    direction = (rotation @ (ob.matrix_world.to_quaternion()
                                             @ Vector((0, 0, 1)))).normalized()
                    records.append(SkyLightRecord(
                        tuple(direction), tuple(ob.data.color), ob.data.energy))
                tag.set_sky_lights(records)
        print(f'--- Wrote {destination}')

    def write_classic_animation_events(self) -> None:
        """Apply Blender metadata after Tool creates the classic animation tag."""
        extension = ('model_animations' if self.target_game == 'halo1'
                     else 'model_animation_graph')
        destination = Path(
            self.tags_dir, self.asset_path_relative, self.asset_name
        ).with_suffix('.' + extension)
        if not destination.is_file():
            raise ExportCancelled(
                f'Animation compilation did not create the expected tag: {destination}')
        animations = {
            animation.name: animation.anim
            for animation in self.virtual_scene.animations
            if (hasattr(animation, 'legacy_tracks')
                or bool(animation.anim.animation_events))
            and animation.name not in self.skipped_legacy_animations
        }
        settings = (tuple(animation for animation in self.anims_for_tag_info
                          if animation.name not in self.skipped_legacy_animations)
                    if self.target_game == 'halo1' else ())
        world_animations = (self.reach_world_animations
                            if self.target_game == 'halo1' else ())
        write_screens = self.scene_settings.blend_screens_from_blender
        if not animations and not settings and not world_animations and not write_screens:
            return
        with AnimationGraphTag(destination) as graph:
            count = (graph.inline_events_from_blender(animations)
                     if animations else 0)
            if settings:
                graph.set_animation_settings(settings)
            if world_animations:
                graph.set_world_animations(world_animations)
            if write_screens:
                try:
                    screen_count = graph.blend_screens_from_blender(
                        self.scene_settings.blend_screens,
                        self.scene_settings.animations,
                    )
                except ValueError as exc:
                    raise ExportCancelled(str(exc)) from exc
        if animations:
            print(f'--- Updated frame events for {count} animation(s) in {destination}')
        if settings:
            print(f'--- Updated animation settings for {len(settings)} animation(s) in {destination}')
        if world_animations:
            print(f'--- Updated {len(world_animations)} world-relative animation(s) in {destination}')
        if write_screens:
            print(f'--- Wrote {screen_count} blend screen(s) in {destination}')

    def create_event_objects(self, animation):
        unsupported = [
            event.event_type for event in animation.animation_events
            if event.event_type != '_connected_geometry_animation_event_type_frame'
        ]
        if unsupported:
            raise ExportCancelled(
                f'{animation.name}: classic animation tags cannot store event types: '
                + ', '.join(sorted(set(unsupported))))
        # JMA has no event channel. Frame events are written into the compiled
        # tag after Tool finishes, using the original Blender animation data.
        return [], []

    def legacy_shader_name(self, mat):
        source_name = getattr(mat, 'legacy_shader_name', '') or mat.name
        path = mat.shader_path
        if self.target_game == 'halo1':
            if source_name.startswith('+'):
                return source_name
            if not path or not path.strip() or path in {'override', 'shaders\\invalid'}:
                self.halo1_shader_paths['invalid'] = INVALID_SHADER_PATH
                return 'invalid'
        if not path or not path.strip() or path == 'override':
            return source_name
        # VirtualMaterial stores the tag class separately from its path.
        # Restore it before resolving the material name and validating the tag.
        shader_type = getattr(mat, 'shader_type', '')
        if shader_type.startswith('shader'):
            path = f'{path}.{shader_type}'
        if path in self.shader_name_cache:
            return self.shader_name_cache[path]
        try:
            name = self.shader_collections.material_name(path)
        except ValueError as exc:
            if path not in self.warned_shader_paths:
                self.warnings.append(f'{mat.name}: {exc}. Using ' + ('invalid shader' if self.target_game == 'halo1' else 'material name'))
                self.warned_shader_paths.add(path)
            return 'invalid' if self.target_game == 'halo1' else source_name
        if self.target_game == 'halo1':
            try:
                filename(name)
            except ValueError:
                if path not in self.warned_shader_paths:
                    self.warnings.append(f'{mat.name}: invalid Halo 1 shader path {path}. Using invalid shader')
                    self.warned_shader_paths.add(path)
                return 'invalid'
        source = Path(self.tags_dir, utils.relative_path(path))
        if self.target_game == 'halo2' and not source.suffix:
            source = source.with_suffix('.shader')
        invalid_source = (not source.is_file()
                          or not source.resolve().is_relative_to(Path(self.tags_dir).resolve())
                          or not source.suffix.lower().startswith('.shader'))
        if invalid_source and path not in self.warned_shader_paths:
            self.warnings.append(f'{mat.name}: shader path is invalid or missing: {path}')
            self.warned_shader_paths.add(path)
        if self.target_game == 'halo1':
            if invalid_source:
                return 'invalid'
            self.halo1_shader_paths[name.casefold()] = source.resolve().relative_to(Path(self.tags_dir).resolve())
        self.shader_name_cache[path] = name
        return name

    def parent_index(self, node, implied_root=False):
        if node.mesh is not None and len(node.mesh.bone_bindings) == 1 and node.mesh.bone_bindings[0] in self.bone_index:
            return self.bone_index[node.mesh.bone_bindings[0]]
        ob = node.ob
        while ob is not None:
            if ob.parent_type == 'BONE' and ob.parent_bone in self.bone_index:
                return self.bone_index[ob.parent_bone]
            ob = ob.parent
        return 0 if self.bones or implied_root else -1

    def face_materials(self, node, asset, cache):
        mesh = node.mesh
        materials = {}
        regions = {v: k for k, v in self.virtual_scene.regions.items()}
        globals_ = {v: k for k, v in self.virtual_scene.global_materials.items()}
        overrides = tuple((key, face_set.array) for key, face_set in mesh.face_properties.items())
        ass_version = asset.version if isinstance(asset, ass.ASS) else None
        permutation = node.permutation or 'default'
        lod = (node.ob.nwo.mesh_lod
               if self.target_game == 'halo2' and node.tag_type == 'render'
               else '')

        def resolve(face, shader):
            props = dict(node.props)
            for key, array in overrides:
                value = array[face]
                props[key] = value.tolist() if hasattr(value, 'tolist') else value
            if ass_version is not None and props.get('bungie_mesh_type') == 13:
                shader = getattr(self, 'portal_material_names', {}).get(id(node), {}).get(shader, shader)
            region = props.get('bungie_face_region', node.region or 'default')
            if not isinstance(region, str):
                region = regions[region]
            gm = props.get('bungie_face_global_material', props.get('bungie_mesh_global_material', 'default'))
            if not isinstance(gm, str):
                gm = globals_[gm]
            if self.supports_bsp:
                gm = 'default'  # Pre-H4 BSP surface types are resolved from shaders.
                if self.target_game in {'halo3', 'halo3odst'}:
                    # Material-authored seams keep their name; Foundry seam
                    # objects (including reversed copies) use their own BSP.
                    if shader.casefold().startswith('+seam:'):
                        props['bungie_mesh_type'] = 14
                    if props.get('bungie_mesh_type') == 14:
                        props.setdefault('bungie_mesh_seam_associated_bsp', node.region or 'default')
            if self.target_game == 'halo1' and props.get('bungie_mesh_type') == 13:
                if node.ob.nwo.is_property_set('portal_exact'):
                    props['foundry_portal_exact'] = node.ob.nwo.portal_exact
            halo1_model = self.target_game == 'halo1' and not self.supports_bsp
            if halo1_model and node.tag_type == 'render' and props.get('bungie_face_sides') in {2, 3, 4, 5, 6, 7}:
                self.halo1_two_sided_shaders.add(shader.casefold())
            if (ass_version is None and self.target_game in {'halo3', 'halo3odst'}
                    and jms_emissive_unsupported(props)):
                warning = f'{node.name}: JMS can store emissive power, but full colour, focus, attenuation and frustum settings require ASS'
                if warning not in self.warnings:
                    self.warnings.append(warning)
            name, lighting = material_variant(shader, props, gm, ass_version, self.target_game,
                                             model=halo1_model)
            if node.tag_type == 'collision':
                # Surface-type names still carry collision sidedness flags.
                # Dropping % loses the opposite side of sheet collision.
                name, _ = material_variant(gm, props, 'default', None, self.target_game)
            elif node.tag_type == 'physics':
                name = gm
            # H2 Tool expects LOD before permutation/region, after an optional
            # Max sub-material ID. An end-of-line LOD is not equivalent.
            definition = (f'{lod} ' if lod else '') + f'{permutation} {region}'
            if self.target_game == 'halo1':
                # H1 stores the optional texture filename here. Regions are
                # triangle records and permutations/LODs are JMS filenames.
                definition = '<none>'
            key = (name, definition, lighting)
            if key not in cache:
                cache[key] = len(asset.materials)
                asset.materials.append(ass.Material(name, definition, lighting) if ass_version is not None
                                       else jms.Material(name, definition, region, permutation, lod.lower()))
            return cache[key], region

        for mat, _, (start, count) in mesh.groups:
            faces = range(int(start), int(start + count))
            if not faces:
                continue
            # Portal materials identify partition groups, never shader tags.
            shader = ((getattr(mat, 'legacy_shader_name', '') or mat.name)
                      if self.target_game in ASS_GAMES and node.props.get('bungie_mesh_type') == 13
                      else self.legacy_shader_name(mat))
            if not overrides:
                materials.update(dict.fromkeys(faces, resolve(faces.start, shader)))
                continue
            # Cache complete override combinations within each material group.
            # Raw array bytes retain integer precision and vector components.
            variants = {}
            if len(faces) >= 32 and all(getattr(array, 'dtype', None) is not None
                                       and array.dtype.kind in 'biufc' for _, array in overrides):
                import numpy as np
                # Group raw bytes rather than coercing mixed attributes to
                # floats. Retain first-use order across bounded batches, since
                # material order affects Tool's processing of geometry.
                for batch_start in range(faces.start, faces.stop, 65536):
                    foundry_output._raise_if_cancel_requested()
                    batch_end = min(batch_start + 65536, faces.stop)
                    count = batch_end - batch_start
                    rows = np.concatenate([
                        np.ascontiguousarray(array[batch_start:batch_end]).view(np.uint8).reshape(count, -1)
                        for _, array in overrides], axis=1)
                    keys = rows.view(np.dtype((np.void, rows.shape[1]))).ravel()
                    _, first, inverse = np.unique(keys, return_index=True, return_inverse=True)
                    resolved = [None] * len(first)
                    for index in np.argsort(first):
                        signature = keys[first[index]].tobytes()
                        if signature not in variants:
                            variants[signature] = resolve(batch_start + int(first[index]), shader)
                        resolved[index] = variants[signature]
                    materials.update(zip(range(batch_start, batch_end),
                                         (resolved[index] for index in inverse.tolist())))
                continue
            for face in faces:
                signature = tuple(array[face].tobytes() for _, array in overrides)
                if signature not in variants:
                    variants[signature] = resolve(face, shader)
                materials[face] = variants[signature]
        unassigned = getattr(node.mesh, 'legacy_no_material', None)
        if unassigned is not None:
            for face, no_material in enumerate(unassigned):
                if no_material:
                    materials[face] = (-1, materials[face][1])
        return materials

    def vertices(self, node, matrix, weighted=True, implied_root=False, *, ass_uvs=False, unit_scale=None):
        mesh = node.mesh
        normal_matrix = matrix.to_3x3().inverted().transposed()
        position_rows = tuple(tuple(row) for row in matrix)[:3]
        unit_scale = self.to_halo_scale if unit_scale is None else unit_scale
        vertices = []
        skinned = weighted and mesh.bone_weights is not None
        palette = tuple(self.bone_index.get(name) for name in mesh.bone_bindings) if skinned else ()
        rigid_influences = ((self.parent_index(node, implied_root), 1),) if (
            weighted and not skinned and (self.bones or implied_root)) else ()
        # Convert array rows in bounded batches, avoiding NumPy scalar iteration
        # without retaining a second full Python copy of the mesh attributes.
        for start in range(0, len(mesh.positions), 1024):
            foundry_output._raise_if_cancel_requested()
            end = start + 1024
            positions = mesh.positions[start:end].tolist()
            normals = mesh.normals[start:end].tolist() if mesh.normals is not None else [(0, 0, 1)] * len(positions)
            colors = mesh.vertex_colors[0][start:end, :3].tolist() if mesh.vertex_colors else None
            uv_layers = [uv[start:end, :3 if ass_uvs else 2].tolist() for uv in mesh.texcoords]
            indices = mesh.bone_indices[start:end].tolist() if skinned else None
            weights = mesh.bone_weights[start:end].tolist() if skinned else None
            for i, position in enumerate(positions):
                influences = rigid_influences
                if skinned:
                    influences = []
                    for index, weight in zip(indices[i], weights[i]):
                        if weight:
                            bone = palette[int(index)]
                            if bone is None:
                                name = mesh.bone_bindings[int(index)]
                                raise ExportCancelled(f'{node.name}: unknown skin bone {name}')
                            influences.append((bone, weight))
                    total = sum(w for _, w in influences)
                    influences = tuple((b, w / total) for b, w in influences)
                normal = normal_matrix @ Vector(normals[i])
                # Authored unit normals need not be normalized a second time
                # in float32. Preserve their precision at rigid transforms.
                if abs(normal.length_squared - 1.0) > 1e-5:
                    normal.normalize()
                # Native text export keeps V in its authoring convention.
                # A float32 1-V round trip destroys small UV components.
                texcoords = tuple(tuple(uv[i]) for uv in uv_layers)
                # Keep conversion arithmetic in double precision until Tool
                # reads the text. A float32 scale/unscale pair moves shared
                # structure vertices by an extra ulp and creates thin slivers.
                output_position = tuple((sum(row[c] * position[c] for c in range(3)) + row[3])
                                        * unit_scale for row in position_rows)
                vertices.append(jms.Vertex(output_position, tuple(normal),
                    influences, texcoords, tuple(colors[i]) if colors is not None else None))
        return vertices

    def xref_record(self, node) -> tuple[str, str, int]:
        """Return the legacy XREF path, object name and signed identifier."""
        tag_path = str(node.props.get('bungie_marker_game_instance_tag_name', '') or
                       node.ob.nwo.marker_game_instance_tag_name or '')
        if not tag_path:
            raise ExportCancelled(f'{node.name}: tag-reference path is missing')
        relative = Path(tag_path.replace('\\', '/'))
        if relative.is_absolute():
            try:
                relative = relative.relative_to(self.tags_dir)
            except ValueError:
                raise ExportCancelled(
                    f'{node.name}: tag-reference path is outside this project: {tag_path}') from None
        elif relative.parts and relative.parts[0].casefold() == 'tags':
            relative = Path(*relative.parts[1:])
        name = relative.stem
        asset_dir = relative.parent
        if asset_dir.name.casefold() != name.casefold():
            asset_dir /= name
        # Tool resolves the current tag reference from a source-model path.
        path = str(Path(self.data_dir, asset_dir, 'render', name + '.max'))
        identity = str(node.props.get('bungie_object_ID', '') or f'{node.name}\0{tag_path}')
        return path, name, utils.id_from_string(identity)

    def marker_group_name(self, node):
        """Use the shared tag group, rather than Blender's unique object name."""
        return node.props.get('bungie_marker_model_group', node.name)

    def marker_permutations(self, node, name, available=None):
        """Resolve a marker's include/exclude scope within this output."""
        nwo = node.ob.nwo
        if not nwo.marker_uses_regions:
            return (name,)
        permutations = {name} if available is None else set(available)
        listed = {p.name for p in nwo.marker_permutations}
        if listed:
            permutations = (permutations - listed if nwo.marker_permutation_type == 'exclude'
                            else permutations & listed)
        return sorted(permutations)

    def jms_asset(self, name, nodes, markers, folder, *, include_physics=False, filter_markers=True):
        asset = jms.JMS(name=name, version=self.jms_version)
        if self.bones:
            for bone in self.bones:
                parent = self.bone_parents[bone.name]
                matrix = bone.matrix_world
                if asset.version < 8205 and parent != -1:
                    matrix = self.bones[parent].matrix_world.inverted() @ matrix
                asset.nodes.append(jms.Node(bone.name, parent, transform(matrix, self.to_halo_scale, asset.version < 8205)))
        else:
            asset.nodes.append(jms.Node(
                'implied_root_node', -1,
                jms.Transform((0, 0, 0, 1), (0, 0, 0))))
        asset.checksum = self.legacy_node_checksum(asset.nodes)
        cache = {}
        for node in nodes:
            foundry_output._raise_if_cancel_requested()
            if self.target_game == 'halo1' and node.tag_type == 'physics':
                # H1 Tool builds mass points from JMS markers, not triangles.
                # Collision meshes share this folder and still need geometry.
                if node.props.get('bungie_mesh_primitive_type') != '_connected_geometry_primitive_type_sphere':
                    raise ExportCancelled(f'{node.name}: Halo 1 physics mass points must be spheres')
                parent = self.parent_index(node, implied_root=True)
                matrix = node.matrix_world
                if parent != -1 and self.bones:
                    matrix = self.bones[parent].matrix_world.inverted() @ matrix
                if not asset.regions:
                    # Tool requires a region even for a marker-only physics JMS.
                    asset.regions.append('default')
                asset.markers.append(jms.Marker(
                    node.name.lstrip('$'), -1, parent,
                    transform(matrix, self.to_halo_scale),
                    float(node.props['bungie_mesh_primitive_sphere_radius'])))
                continue
            materials = self.face_materials(node, asset, cache)
            if (folder == 'physics' or (include_physics and node.tag_type == 'physics')) and self.jms_version >= 8206:
                if len({m[0] for m in materials.values()}) > 1:
                    raise ExportCancelled(f'{node.name}: split physics shapes with different collision materials into separate objects')
                parent = self.parent_index(node, implied_root=True)
                matrix = node.matrix_world
                if parent != -1 and self.bones:
                    matrix = self.bones[parent].matrix_world.inverted() @ matrix
                material = next(iter(materials.values()), (-1, 'default'))[0]
                primitive = node.props.get(
                    'bungie_mesh_primitive_type',
                    '_connected_geometry_primitive_type_none')
                dimensions = ()
                kind = 'convex'
                if primitive == '_connected_geometry_primitive_type_sphere':
                    kind = 'sphere'
                    dimensions = (float(node.props['bungie_mesh_primitive_sphere_radius']),)
                elif primitive == '_connected_geometry_primitive_type_box':
                    kind = 'box'
                    dimensions = tuple(float(node.props[name]) for name in (
                        'bungie_mesh_primitive_box_width',
                        'bungie_mesh_primitive_box_length',
                        'bungie_mesh_primitive_box_height'))
                elif primitive == '_connected_geometry_primitive_type_pill':
                    kind = 'pill'
                    radius = float(node.props['bungie_mesh_primitive_pill_radius'])
                    total_height = float(node.props['bungie_mesh_primitive_pill_height'])
                    dimensions = (max(0.0, total_height - radius * 2.0), radius)
                if kind != 'convex':
                    valid_dimensions = (dimensions[-1] > 0.0 if kind == 'pill'
                                        else bool(dimensions) and all(
                                            value > 0.0 for value in dimensions))
                    if not valid_dimensions:
                        raise ExportCancelled(
                            f'{node.name}: {kind} physics dimensions must be positive')
                    shape_transform = transform(matrix, self.to_halo_scale)
                    asset.shapes.append(jms.Shape(
                        kind, node.name.lstrip('$'), parent, material,
                        shape_transform, dimensions=dimensions))
                else:
                    # Convex records can represent arbitrary evaluated physics meshes.
                    points = tuple(v.position for v in self.vertices(node, matrix, False))
                    asset.shapes.append(jms.Shape('convex', node.name, parent, material,
                        jms.Transform((0, 0, 0, 1), (0, 0, 0)), vertices=points))
                continue
            offset = len(asset.vertices)
            asset.vertices.extend(self.vertices(node, node.matrix_world, implied_root=True))
            for face, triangle in enumerate(node.mesh.indices.reshape((-1, 3))):
                material, region = materials[face]
                if region not in asset.regions:
                    asset.regions.append(region)
                indices = tuple(int(i) + offset for i in triangle)
                if node.negative_scaling:
                    indices = indices[0], indices[2], indices[1]
                asset.triangles.append(jms.Triangle(material, indices, asset.regions.index(region)))
        if (folder == 'physics' or include_physics) and self.jms_version >= 8206:
            for node in markers:
                marker_type = node.props.get('bungie_marker_type')
                if marker_type not in {
                        '_connected_geometry_marker_type_physics_hinge_constraint',
                        '_connected_geometry_marker_type_physics_socket_constraint'}:
                    continue
                parent_name = node.props.get('bungie_physics_constraint_parent', '')
                child_name = node.props.get('bungie_physics_constraint_child', '')
                parent = self.bone_index.get(parent_name, -1)
                child = self.bone_index.get(child_name, -1)
                if parent < 0 or child < 0:
                    raise ExportCancelled(
                        f'{node.name}: physics constraint endpoints must name '
                        'bones in the exported skeleton')
                parent_matrix = self.bones[parent].matrix_world.inverted() @ node.matrix_world
                child_matrix = self.bones[child].matrix_world.inverted() @ node.matrix_world
                use_limits = bool(node.props.get(
                    'bungie_physics_constraint_use_limits', 0))
                if marker_type.endswith('hinge_constraint'):
                    kind = 'hinge'
                    limits = (
                        int(use_limits), 0.0,
                        float(node.props.get('bungie_physics_constraint_hinge_min', 0.0)),
                        float(node.props.get('bungie_physics_constraint_hinge_max', 0.0)),
                    )
                else:
                    kind = 'ragdoll'
                    limits = (
                        float(node.props.get('bungie_physics_constraint_twist_start', 0.0)),
                        float(node.props.get('bungie_physics_constraint_twist_end', 0.0)),
                        0.0,
                        float(node.props.get('bungie_physics_constraint_cone_angle', 0.0)),
                        float(node.props.get('bungie_physics_constraint_plane_min', 0.0)),
                        float(node.props.get('bungie_physics_constraint_plane_max', 0.0)),
                    ) if use_limits else (0.0,) * 6
                    if self.jms_version >= 8213:
                        limits += (0.0,)
                asset.constraints.append(jms.Constraint(
                    kind, node.name.lstrip('$'), parent, child,
                    transform(parent_matrix, self.to_halo_scale),
                    transform(child_matrix, self.to_halo_scale), limits))
        # Structure markers belong to their BSP and are part of structure
        # export; model marker options and permutation scopes do not apply.
        structure_markers = folder == 'structure'
        if structure_markers or ((folder in {'render', 'models', 'collision'} or include_physics)
                                 and 'markers' in self.export_tag_types):
            xref_indices = {}
            merged_render = folder == 'render' and self.target_game in {'halo3', 'halo3odst'}
            region_permutations = defaultdict(set)
            for material in asset.materials:
                region_permutations[material.region].add(material.permutation)
            for node in markers:
                if structure_markers and node.region != asset.name:
                    continue
                nwo = node.ob.nwo
                collision_marker = nwo.marker_type == '_connected_geometry_marker_type_pathfinding_sphere'
                physics_marker = nwo.marker_type == '_connected_geometry_marker_type_physics_constraint'
                if ((folder == 'collision' and not collision_marker) or
                        (folder != 'collision' and (collision_marker or physics_marker))):
                    continue
                scoped_permutations = (name,)
                if not structure_markers and (filter_markers or self.jms_version >= 8205):
                    available = (self.permutations if not filter_markers else
                                 region_permutations[node.region or 'default'] if merged_render else None)
                    scoped_permutations = self.marker_permutations(node, name, available)
                    if not scoped_permutations:
                        continue
                if nwo.marker_type == '_connected_geometry_marker_type_game_instance':
                    try:
                        path, xref_name, identifier = self.xref_record(node)
                    except ValueError as exc:
                        self.warnings.append(f'{exc}. Skipping marker')
                        continue
                    key = path.casefold(), xref_name.casefold()
                    xref_index = xref_indices.get(key)
                    if xref_index is None:
                        xref_index = len(asset.xrefs)
                        xref_indices[key] = xref_index
                        asset.xrefs.append((path, xref_name))
                    asset.instances.append((node.name, identifier, xref_index,
                                            transform(node.matrix_world, self.to_halo_scale)))
                    continue
                parent = self.parent_index(node, implied_root=True)
                matrix = node.matrix_world
                if parent != -1 and self.bones:
                    matrix = self.bones[parent].matrix_world.inverted() @ matrix
                region = node.region or 'default'
                uses_regions = nwo.marker_uses_regions and not structure_markers
                if not structure_markers and region not in asset.regions:
                    asset.regions.append(region)
                group_name = self.marker_group_name(node)
                for permutation in scoped_permutations:
                    marker_name = f'({permutation} {region}){group_name}' if uses_regions and self.jms_version >= 8205 else group_name
                    asset.markers.append(jms.Marker(marker_name, asset.regions.index(region) if uses_regions else -1,
                        parent, transform(matrix, self.to_halo_scale), node.props.get('bungie_mesh_primitive_sphere_radius', 1)))
        if self.target_game == 'halo1' and folder == 'physics' and asset.markers and not asset.materials:
            # Tool also requires a material to build its intermediate model,
            # even though mass points do not reference any faces or shaders.
            asset.materials.append(jms.Material('default', '<none>'))
        if self.asset_type.name in {'PARTICLE_MODEL', 'DECORATOR_SET'}:
            asset_label = self.asset_type.name.lower().replace('_', '-')
            vertex_bones = []
            for vertex in asset.vertices:
                influences = [bone for bone, weight in vertex.influences
                              if bone >= 0 and weight > 0.0]
                if len(influences) != 1:
                    raise ExportCancelled(
                        f'H2 {asset_label} geometry must be rigid; each vertex '
                        'must have exactly one bone influence')
                vertex_bones.append(influences[0])
            section_bones = defaultdict(set)
            for triangle in asset.triangles:
                section_bones[(triangle.region, triangle.material)].update(
                    vertex_bones[index] for index in triangle.vertices)
            if any(len(bones) != 1 for bones in section_bones.values()):
                raise ExportCancelled(
                    f'H2 {asset_label} geometry must be rigid; each material '
                    'section must use one bone')
        if self.target_game == 'halo1' and folder == 'structure':
            from ..legacy.portal_geometry import planarize_halo1_portals
            from ..legacy.structure_geometry import stabilize_halo1_collision_slivers
            corrected = planarize_halo1_portals(asset)
            # if corrected:
            #     utils.print_step(f'Stabilized {corrected} portal plane(s)')
            repaired = stabilize_halo1_collision_slivers(asset)
            if repaired:
                utils.print_step(f'Stabilized {repaired} thin sky collision surface(s)')
        return asset

    def ass_asset(self, name, nodes, markers=(), lights=(), *, filter_region=True,
                  filter_markers=True):
        if self.target_game in ASS_GAMES:
            for marker in markers:
                if marker.ob.nwo.marker_type == '_connected_geometry_marker_type_game_instance':
                    path = marker.ob.nwo.marker_game_instance_tag_name
                    if Path(path).suffix.casefold() not in ASS_GAME_OBJECT_EXTENSIONS:
                        raise ExportCancelled(f'{marker.name}: ASS game objects support only scenery and device_machine tags; got {path!r}')
        asset = ass.ASS(name=name, version=self.ass_version)
        cache, geometries = {}, {}
        node_instances = {}
        from ..legacy.ass_hierarchy import AssHierarchy
        hierarchy = AssHierarchy(asset, self.virtual_scene.depsgraph, self.to_halo_scale, self.rotation_correction) if self.supports_bsp else None
        hierarchy_nodes = {}
        asset.instances.append(ass.Instance(-1, 'frame', -1, -1, 0, ass.Transform(), ass.Transform()))
        for bone in self.bones:
            parent = self.bone_parents[bone.name]
            matrix = bone.matrix_world
            if parent != -1:
                matrix = self.bones[parent].matrix_world.inverted() @ matrix
            value = transform(matrix, self.to_halo_scale)
            asset.instances.append(ass.Instance(-1, bone.name, len(asset.instances), parent + 1,
                0, ass.Transform(value.rotation, value.translation), ass.Transform()))
        # Proxy meshes refer to their render instance by parent index, so emit
        # ordinary nodes first even if the virtual-scene dictionary order was
        # changed by evaluation.
        ordered_nodes = sorted(nodes, key=lambda node: node.proxy_parent is not None)
        from ..legacy.portal_groups import allocate_portal_materials
        self.portal_material_names = allocate_portal_materials(
            (id(node), node.props.get('foundry_portal_group_index', -1),
             tuple(getattr(mat, 'legacy_shader_name', '') or mat.name for mat, _, _ in node.mesh.groups))
            for node in ordered_nodes
            if self.target_game in ASS_GAMES and node.props.get('bungie_mesh_type') == 13)
        for node in ordered_nodes:
            foundry_output._raise_if_cancel_requested()
            materials = self.face_materials(node, asset, cache)
            matrix = (Matrix.Identity(4) if node.proxy_parent is not None
                      else node.matrix_world)
            loc, rot, scale = matrix.decompose()
            uniform = max(scale) - min(scale) < 1e-5 and abs(scale[0]) > 0
            rebuilt = Matrix.LocRotScale(loc, rot, scale)
            uniform = uniform and max(abs(matrix[r][c] - rebuilt[r][c]) for r in range(4) for c in range(4)) < 1e-5
            local = ass.Transform((rot.x, rot.y, rot.z, rot.w),
                                  tuple(c * self.to_halo_scale for c in loc),
                                  tuple(scale)) if uniform else ass.Transform()
            pivot = ass.Transform()
            placement = hierarchy.placement(node) if hierarchy is not None and node.proxy_parent is None else None
            local_units = placement is not None or (node.proxy_parent is not None and id(node.proxy_parent) in hierarchy_nodes)
            mesh_units = None
            if placement is not None:
                hierarchy_parent, local, pivot, mesh_units = placement
                uniform = True
                hierarchy_nodes[id(node)] = (pivot, mesh_units)
            elif local_units:
                _, mesh_units = hierarchy_nodes[id(node.proxy_parent)]
            key = (id(node.mesh), tuple(m[0] for m in materials.values()), node.negative_scaling, mesh_units)
            geometry_index = geometries.get(key) if uniform else None
            if geometry_index is None:
                geometry = ass.Geometry('MESH')
                geometry.vertices = self.vertices(node, Matrix.Identity(4) if uniform else matrix, bool(self.bones),
                                                  ass_uvs=self.ass_version >= 5, unit_scale=mesh_units)
                palette = sorted({b for vertex in geometry.vertices for b, _ in vertex.influences})
                palette_map = {b: i for i, b in enumerate(palette)}
                for vertex in geometry.vertices:
                    vertex.influences = tuple((palette_map[b], weight) for b, weight in vertex.influences)
                geometry.node_indices = list(range(len(palette)))
                triangles = node.mesh.indices.reshape((-1, 3))
                face_order = getattr(node.mesh, 'legacy_face_order', None)
                for face in range(len(triangles)) if face_order is None else face_order:
                    triangle = triangles[face]
                    indices = tuple(int(i) for i in triangle)
                    if node.negative_scaling and not (uniform and (node.matrix_world.is_negative if local_units else scale[0] < 0)):
                        indices = indices[0], indices[2], indices[1]
                    geometry.triangles.append(jms.Triangle(materials[face][0], indices))
                try:
                    removed, repaired = clean_ass_mesh(geometry,
                        preserve_degenerate=self.target_game in ASS_GAMES and self.supports_bsp)
                except ValueError as error:
                    raise ExportCancelled(f'{node.name}: {error}') from error
                if not geometry.triangles:
                    raise ExportCancelled(f'{node.name}: ASS mesh has no non-degenerate triangles')
                # if removed or repaired:
                #     self.warnings.append(
                #         f'{node.name}: removed {removed} zero-area ASS triangles '
                #         f'and recovered {repaired} invalid vertex normals')
                geometry_index = len(asset.geometries)
                asset.geometries.append(geometry)
                if uniform:
                    geometries[key] = geometry_index
                geometry_bones = tuple(b + 1 for b in palette)
            else:
                geometry_bones = next(i.bones for i in asset.instances if i.geometry == geometry_index)
            mesh_type = node.props.get('bungie_mesh_type')
            instance_name = legacy_instance_name(node.name, node.props, mesh_type, self.target_game)
            if node.props.get('foundry_weather_polyhedron'):
                if not instance_name.casefold().startswith('+weather'):
                    suffix = instance_name.rpartition(':')[2].lstrip('+')
                    instance_name = '+weather_' + (suffix or str(len(asset.instances)))
            parent = node_instances.get(id(node.proxy_parent), 0)
            if placement is not None:
                parent = hierarchy_parent
            if node.proxy_parent is not None:
                # Proxy coordinates are already local to the owning instance.
                local = hierarchy_nodes[id(node.proxy_parent)][0] if local_units else ass.Transform()
            instance_index = len(asset.instances)
            asset.instances.append(ass.Instance(geometry_index, instance_name, instance_index,
                parent, 0, local, pivot, geometry_bones))
            node_instances[id(node)] = instance_index
        if 'markers' in self.export_tag_types or self.supports_bsp:
            xref_geometries = {}
            merged_render = self.target_game in {'halo3', 'halo3odst'}
            region_permutations = defaultdict(set)
            for material in asset.materials:
                region, permutation = material.region_permutation()
                region_permutations[region].add(permutation)
            for node in markers:
                if filter_region and self.supports_bsp and node.region != name:
                    continue
                nwo = node.ob.nwo
                scoped_permutations = (name,)
                if not self.supports_bsp:
                    available = (self.permutations if not filter_markers else
                                 region_permutations[node.region or 'default'] if merged_render else None)
                    scoped_permutations = self.marker_permutations(node, name, available)
                    if not scoped_permutations:
                        continue
                if nwo.marker_type == '_connected_geometry_marker_type_game_instance':
                    try:
                        path, xref_name, identifier = self.xref_record(node)
                    except ValueError as exc:
                        self.warnings.append(f'{exc}. Skipping marker')
                        continue
                    key = path.casefold(), xref_name.casefold()
                    geometry_index = xref_geometries.get(key)
                    if geometry_index is None:
                        geometry_index = len(asset.geometries)
                        xref_geometries[key] = geometry_index
                        asset.geometries.append(ass.Geometry('MESH', xref_path=path, xref_name=xref_name))
                    value = transform(node.matrix_world, self.to_halo_scale)
                    instance_name = ass_reference_prefix(nwo.marker_game_instance_tag_name) + ass_reference_name(node.name)
                    asset.instances.append(ass.Instance(
                        geometry_index, instance_name, identifier, 0, 0,
                        ass.Transform(value.rotation, value.translation), ass.Transform(),
                        tuple(-1 for _ in asset.geometries[geometry_index].node_indices)))
                    continue
                parent = self.parent_index(node)
                matrix = node.matrix_world
                if parent != -1:
                    matrix = self.bones[parent].matrix_world.inverted() @ matrix
                value = transform(matrix, self.to_halo_scale)
                group_name = self.marker_group_name(node)
                marker_name = '#' + group_name
                for permutation in scoped_permutations:
                    marker_name = (f'#({permutation} {node.region or "default"}){group_name}'
                                   if nwo.marker_uses_regions and not self.supports_bsp else '#' + group_name)
                    asset.instances.append(ass.Instance(-1, marker_name, len(asset.instances), parent + 1,
                        0, ass.Transform(value.rotation, value.translation), ass.Transform()))
        for ob in lights:
            data = ob.data
            nwo = data.nwo
            kind = {
                'POINT': 'OMNI_LGT', 'SPOT': 'SPOT_LGT',
                'AREA': 'DIRECT_LGT', 'SUN': 'AMBIENT_LGT',
            }.get(data.type)
            if kind is None:
                self.warnings.append(f'{ob.name}: unsupported legacy light type {data.type}. Skipping light')
                continue
            hotspot = falloff = 0.0
            shape = 0
            aspect = 1.0
            if data.type == 'SPOT':
                falloff = degrees(data.spot_size)
                hotspot = falloff * (1.0 - data.spot_blend)
            elif data.type == 'AREA':
                hotspot = data.size * self.to_halo_scale
                shape = int(data.shape in {'RECTANGLE', 'SQUARE'})
                if data.shape == 'RECTANGLE':
                    aspect = data.size / max(data.size_y, 1e-6)
            near_start = float(getattr(nwo, 'light_near_attenuation_start', 0.0))
            near_end = float(getattr(nwo, 'light_near_attenuation_end', 0.0))
            far_start = float(nwo.light_far_attenuation_start)
            far_end = float(nwo.light_far_attenuation_end)
            light = ass.Light(
                kind, tuple(data.color), float(data.energy), hotspot, falloff,
                int(near_end > 0.0), near_start * self.to_halo_scale,
                near_end * self.to_halo_scale, int(far_end > 0.0),
                far_start * self.to_halo_scale, far_end * self.to_halo_scale,
                shape, aspect,
            )
            geometry_index = len(asset.geometries)
            asset.geometries.append(ass.Geometry('GENERIC_LIGHT', light=light))
            matrix = self.virtual_scene.rotation_matrix @ ob.matrix_world
            value = transform(matrix, self.to_halo_scale)
            asset.instances.append(ass.Instance(
                geometry_index, ob.name, len(asset.instances), 0, 0,
                ass.Transform(value.rotation, value.translation), ass.Transform()))
        if self.target_game in ASS_GAMES and self.supports_bsp:
            # Tool selects the first authored frame beneath the scene wrapper.
            # Keep geometry, references and lights within that same export frame:
            # root-level siblings of retained source frames are otherwise culled.
            for instance in asset.instances:
                if instance.parent >= 0:
                    instance.parent += 1
                instance.bones = tuple(bone + 1 if bone >= 0 else bone for bone in instance.bones)
            asset.instances[0].name = 'Scene Root'
            asset.instances.insert(1, ass.Instance(-1, 'frame ' + name, 0, 0, 0,
                                                  ass.Transform(), ass.Transform()))
        return asset

    @staticmethod
    def animation_extension(animation):
        if animation.overlay:
            return '.jmo'
        if animation.animation_type == 'replacement':
            return '.jmrx' if getattr(animation, 'space', 'object') == 'local' else '.jmr'
        return {'none': '.jmm', 'xy': '.jma', 'xyyaw': '.jmt', 'xyzyaw': '.jmz', 'full': '.jmv'}[animation.movement]

    def legacy_node_checksum(self, nodes):
        if not self.export_settings.legacy_generate_checksum:
            return self.export_settings.legacy_file_checksum
        return node_checksum(
            nodes, halo1=self.target_game == 'halo1',
            maya_order=self.export_settings.legacy_maya_order)

    def export_cinematic_shots(self, write_intermediates):
        """Keep camera data in memory; Tool consumes one JMM folder per actor."""
        self.cinematic_scene.shots = self.virtual_scene.shots
        outputs = []
        inventories = defaultdict(set)
        skeletons = set()
        for shot in self.virtual_scene.shots:
            for shot_actor, animation in shot.actor_animation.items():
                actor = shot_actor.actor
                if actor.scenario_only:
                    continue
                self.cinematic_scene.actor_animations[actor].append(animation)
                source_dir = Path(self.asset_path, 'objects', self.cinematic_scene.name, filename(actor.name))
                actor.graph = str(source_dir.relative_to(self.data_dir) / f'{actor.name}.model_animation_graph')
                source = source_dir / 'animations' / (filename(animation.name) + '.jmm')
                inventories[source_dir].add(source)
                if not shot.in_scope or not shot_actor.in_scope:
                    continue
                self.cinematic_graph_actors[actor.graph] = actor
                if not write_intermediates:
                    if not source.is_file():
                        raise ExportCancelled(f'No cinematic animation source was found: {source}. Run Full Export first')
                    if not (source_dir / 'render' / f'{actor.name}.jms').is_file():
                        raise ExportCancelled(f'No cinematic skeleton source was found for {actor.name}. Run Full Export first')
                    continue
                bones = list(shot_actor.bones or ())
                if not actor.node_order or {bone.name for bone in bones} != set(actor.node_order):
                    raise ExportCancelled(f'{actor.name}: cinematic skeleton must match the actor render model nodes')
                bones.sort(key=lambda bone: actor.node_order[bone.name])
                indices = {bone.name: index for index, bone in enumerate(bones)}
                parents = {bone.name: indices.get(bone.parent.name, -1) if bone.parent else -1 for bone in bones}
                if source_dir not in skeletons:
                    outputs.append((source_dir / 'render' / f'{actor.name}.jms', self.cinematic_skeleton(actor)))
                    skeletons.add(source_dir)
                # Tool removes the terminal held sample from base/JMM sources.
                # Include it so graph and camera shot lengths remain identical.
                held_tracks = [(name, [*positions, *positions[-3:]],
                                [*rotations, *rotations[-4:]], [*scales, *scales[-9:]])
                               for name, positions, rotations, scales in animation.legacy_tracks]
                held = SimpleNamespace(name=animation.name, frame_count=animation.frame_count + 1,
                                       legacy_tracks=held_tracks)
                outputs.append((source, self.jma_text(held, bones=bones, bone_parents=parents)))
        if not write_intermediates:
            return
        write_outputs(outputs, maya_order=self.export_settings.legacy_maya_order)
        if not self.current_shot_only and not self.selected_cinematic_objects_only:
            for source_dir, expected in inventories.items():
                if self.export_settings.cinematic_scope != 'CAMERA':
                    prune_intermediates(source_dir, expected, {source_dir / 'animations': ANIMATION_EXTENSIONS})

    def cinematic_skeleton(self, actor):
        """Tool requires a render JMS even when only compiling an actor graph."""
        if actor.render_model is None:
            bones = [actor.ob.data.bones[name] for name in actor.node_order]
            skeleton = jms.JMS(name=actor.name, version=self.jms_version)
            rotation = self.virtual_scene.rotation_matrix
            skeleton.nodes = [jms.Node(bone.name,
                actor.node_order.get(bone.parent.name, -1) if bone.parent else -1,
                transform(rotation @ actor.ob.matrix_world @ bone.matrix_local, self.to_halo_scale))
                for bone in bones]
            skeleton.checksum = self.legacy_node_checksum(skeleton.nodes)
            return skeleton
        with RenderModelMetadataTag(path=Path(actor.render_model).with_suffix('.render_model')) as model:
            nodes = model.nodes()
        world = {}

        def world_matrix(index):
            if index not in world:
                node = nodes[index]
                x, y, z, w = node.rotation
                local = Matrix.LocRotScale(Vector(node.translation) * 100,
                    Quaternion((w, x, y, z)), Vector((1, 1, 1)))
                world[index] = world_matrix(node.parent_index) @ local if node.parent_index != -1 else local
            return world[index]

        skeleton = jms.JMS(name=actor.name, version=self.jms_version)
        skeleton.nodes = [jms.Node(node.name, node.parent_index, transform(world_matrix(index)))
                          for index, node in enumerate(nodes)]
        skeleton.checksum = self.legacy_node_checksum(skeleton.nodes)
        return skeleton

    def write_cinematic_graphs(self):
        if self.export_settings.cinematic_scope == 'CAMERA':
            return
        for graph_path, actor in self.cinematic_graph_actors.items():
            source_dir = Path(graph_path).parent
            destination = Path(self.tags_dir, graph_path)
            if destination.is_file():
                with AnimationGraphTag(path=graph_path) as graph:
                    set_actor_animation_compression(graph, actor)
            print(f'--- Compiling cinematic animation graph: {actor.name}')
            self._run_import_tool(['model-animations', source_dir], event_level=self.export_settings.event_level)
            destination = Path(self.tags_dir, graph_path)
            if not destination.is_file():
                raise ExportCancelled(f'Tool did not create the cinematic animation graph: {destination}')
            with AnimationGraphTag(path=graph_path) as graph:
                expected = {animation.name for scene in self.cinematic_scenes
                            for candidate, animations in scene.actor_animations.items()
                            if candidate.graph == graph_path for animation in animations}
                missing = expected - set(graph.animation_names())
                if missing:
                    raise ExportCancelled(f'{actor.name}: Tool did not compile cinematic animations: {", ".join(sorted(missing))}')
                if graph.get_nodes() != list(actor.node_order or ()):
                    raise ExportCancelled(f'{actor.name}: compiled cinematic skeleton does not match the render model')
                compression_changed = set_actor_animation_compression(graph, actor)
            if compression_changed:
                # New shot animations only acquire entries on the first compilation.
                self._run_import_tool(['model-animations', source_dir], event_level=self.export_settings.event_level)
                with AnimationGraphTag(path=graph_path) as graph:
                    set_actor_animation_compression(graph, actor)

    def jma_text(self, animation, *, bones=None, bone_parents=None):
        bones = self.bones if bones is None else bones
        bone_parents = self.bone_parents if bone_parents is None else bone_parents
        tracks = {name: (positions, rotations, scales) for name, positions, rotations, scales in animation.legacy_tracks}
        stream = io.StringIO()
        w = TextWriter(stream, decimal_places=6 if self.target_game == 'halo1' else None)
        nodes = hierarchy([jms.Node(b.name, bone_parents[b.name], jms.Transform((0, 0, 0, 1), (0, 0, 0))) for b in bones], halo1=self.target_game == 'halo1', maya_order=self.export_settings.legacy_maya_order)
        w.line(self.jma_version)
        if self.jma_version >= 16394:
            w.line(self.legacy_node_checksum(nodes))
        for value in (animation.frame_count, round(1 / self.virtual_scene.time_step), 1, self.asset_name, len(bones)):
            w.line(value)
        if self.jma_version < 16394:
            w.line(self.legacy_node_checksum(nodes))
        for node in nodes:
            w.line(node.name)
            if self.jma_version >= 16394:
                w.line(node.parent)
            else:
                w.line(node.child)
                w.line(node.sibling)
        for frame in range(animation.frame_count):
            world = {}

            def world_matrix(bone):
                if bone.name in world:
                    return world[bone.name]
                positions, rotations, scales = tracks[bone.name]
                scale = [scales[frame * 9 + i] for i in (0, 4, 8)]
                x, y, z, q = rotations[frame * 4:frame * 4 + 4]
                matrix = Matrix.LocRotScale(Vector(positions[frame * 3:frame * 3 + 3]), Quaternion((q, x, y, z)), Vector(scale))
                parent = bone_parents[bone.name]
                world[bone.name] = (world_matrix(bones[parent]) @ matrix
                                    if self.jma_version >= 16394 and parent != -1 else matrix)
                return world[bone.name]

            for bone in bones:
                matrix = world_matrix(bone)
                value = transform(matrix, self.to_halo_scale, self.jma_version <= 16394)
                if self.mirror:
                    mirror_transform(value)
                w.vector(value.translation)
                w.vector(value.rotation)
                output_scale = matrix.to_scale()[0]
                if self.target_game == 'halo1':
                    output_scale = round(output_scale, 2)
                w.vector((output_scale,))
        if self.jma_version >= 16395:
            w.line(0)  # No separate biped-controller track.
        return stream.getvalue()


def export_legacy_cinematic(export, collection_view_layer=None):
    """H3/ODST cinematics write native tags and compile actor graphs explicitly."""
    context = export.context
    scene_settings = export.scene_settings
    settings = export.export_settings
    start_scene = context.scene
    scenes = []
    seen = set()
    export.cinematic_graph_actors = {}
    try:
        for index, item in enumerate(scene_settings.cinematic_scenes):
            if not item.name.strip() or item.scene is None or item.scene not in set(bpy.data.scenes):
                utils.print_warning(f'Cinematic Scene Index {index} has no valid scene ID or Blender scene, skipping')
                continue
            filename(f'{export.asset_name}_{item.name}')
            if item.scene not in seen:
                scenes.append(item)
                seen.add(item.scene)
        selected = [item for item in scenes if not settings.current_scene_only or item.scene == start_scene]
        if not selected:
            raise ExportCancelled('No valid scenes to export')
        names = [f'{export.asset_name}_{item.name}'.casefold() for item in scenes]
        if len(names) != len(set(names)):
            raise ExportCancelled('Cinematic scene IDs must be unique')
        for item in selected:
            if context.scene != item.scene:
                context.window.scene = item.scene
            export.new_scene(item.name, item)
            try:
                export.ready_scene(collection_view_layer)
                export.get_initial_export_objects()
                export.map_halo_properties()
                export.set_template_node_order()
                export.create_virtual_tree()
                export.sample_shots()
                export.export_cinematic_shots(settings.export_mode in {'FULL', 'GRANNY'})
                export.report_warnings()
            finally:
                export.restore_scene()
        # Retain the root's complete scene list during a current-scene export.
        processed = {scene.scene: scene for scene in export.cinematic_scenes}
        export.cinematic_scenes = [processed.get(item.scene) or CinematicScene(
            export.asset_path_relative, f'{export.asset_name}_{item.name}',
            item.scene, item, scene_settings) for item in scenes]
        if settings.export_mode in {'FULL', 'TAGS'}:
            export.write_cinematic_graphs()
            export.postprocess_tags()
    finally:
        if context.scene != start_scene:
            from . import _schedule_scene_restore
            _schedule_scene_restore(context.window, start_scene)
        os.chdir(export.original_cwd)


def export_legacy_asset(context, asset_name, asset_path, scene_settings, export_settings, single_animation, collection_view_layer=None):
    project = utils.get_project(scene_settings.scene_project)
    if not project or project.game not in VERSIONS:
        raise ExportCancelled('JMS/ASS export requires an H1, H2, H3 or ODST project')
    from ..game_capabilities import validate_legacy_animation
    if (scene_settings.asset_type in {'model', 'sky', 'animation', 'single_animation'}
            and export_settings.export_animations != 'NONE'):
        if project.game == 'halo1' and scene_settings.parent_animation_graph.strip():
            raise ExportCancelled('Halo 1 does not support parent animation graphs. Clear the saved parent graph path')
        try:
            if single_animation:
                validate_legacy_animation(scene_settings, project.game, asset_name)
            else:
                animations = list(scene_settings.animations)
                if export_settings.export_animations == 'ACTIVE':
                    index = scene_settings.active_animation_index
                    animations = animations[index:index + 1] if index >= 0 else []
                for animation in animations:
                    if animation.export_this:
                        validate_legacy_animation(animation, project.game, animation.name)
        except ValueError as exc:
            raise ExportCancelled(str(exc)) from exc
    cinematic = scene_settings.asset_type == 'cinematic' and project.game in {'halo3', 'halo3odst'}
    if not cinematic and scene_settings.asset_type not in {'model', 'sky', 'scenario', 'prefab', 'particle_model', 'decorator_set', 'animation', 'single_animation', 'multi_model', 'multi_prefab'}:
        raise ExportCancelled(f'JMS/ASS export does not support {scene_settings.asset_type} assets')
    single_name = Path(bpy.data.filepath).stem if single_animation else ''
    if single_animation and project.game == 'halo1' and len(single_name) >= 32:
        utils.print_warning(f'{single_name}: Halo 1 animation names must be shorter than 32 characters. Skipping animation')
        return
    write_intermediates = export_settings.export_mode in {'FULL', 'GRANNY'}
    write_tags = export_settings.export_mode in {'FULL', 'TAGS'}
    if not asset_path and single_animation:
        asset_path = str(Path(bpy.data.filepath).parent.parent)
    path = Path(asset_path).resolve()
    # Keep tag names and paths tied to the selected legacy asset folder even if
    # an operator entered with a stale ExportHelper filename.
    asset_name = path.name
    data = Path(utils.get_data_path()).resolve()
    if not path.is_relative_to(data) or path == data:
        raise ExportCancelled('Legacy exports must be inside an asset folder below the project data directory')
    ensure_asset_marker(path, data, scene_settings)
    export = LegacyExportScene(context, '', '', scene_settings.asset_type, asset_name, str(path), False,
                               export_settings, scene_settings, context.scene)
    if cinematic:
        return export_legacy_cinematic(export, collection_view_layer)
    export.new_scene('default')
    try:
        export.ready_scene(collection_view_layer)
        export.get_initial_export_objects()
        export.map_halo_properties()
        if project.game == 'halo1' and not single_animation and scene_settings.asset_type != 'scenario':
            export.prepare_halo1_material_shaders('shader_model')
        if project.game == 'halo2':
            export.prepare_halo2_water()
            export.prepare_halo2_material_emissives(write_intermediates, write_tags)
        if write_intermediates:
            # Legacy serializers apply a shared deterministic order without tag templates.
            export.create_virtual_tree()
            export.sample_animations(single_animation)
            wrote_intermediates = export.export_legacy(single_animation)
            export.report_warnings()
            if single_animation and not wrote_intermediates:
                write_tags = False
    finally:
        try:
            export.restore_scene()
        finally:
            os.chdir(export.original_cwd)

    if write_tags:
        try:
            warnings_before_tags = len(export.warnings)
            # Classic scenario compilation creates the scenario tag later in
            # write_tags, so it cannot be opened during preprocessing.
            classic_scenario = (scene_settings.asset_type == 'scenario'
                                and project.game in {'halo1', 'halo2'})
            if project.game != 'halo1' and not classic_scenario:
                export.preprocess_tags()
            export.write_tags(single_animation)
            if project.game != 'halo1':
                export.postprocess_tags()
            elif classic_scenario:
                export.update_scenario_skies()
                export.export_scenario_decals()
                export.export_scenario_marker_tags()
            if (project.game in {'halo1', 'halo2'} and scene_settings.asset_type == 'scenario' and
                    export_settings.lightmap_structure):
                scenario_path = Path(export.asset_path_relative, export.asset_name)
                scenario_tag = Path(export.tags_dir, scenario_path).with_suffix('.scenario')
                with ScenarioDocument(scenario_tag, tags_root=export.tags_dir,
                                      game=project.game) as scenario:
                    block = scenario.block(scenario.tag.root(), 'structure bsps')
                    bsps = [reference.ShortName for entry in block
                            if (reference := scenario.reference(entry, 'structure bsp')) is not None]
                if not export_settings.lightmap_all_bsps:
                    bsp = export_settings.lightmap_specific_bsp
                    if bsp not in bsps:
                        raise ExportCancelled(f'Specified BSP [{bsp}] does not exist in {scenario_tag}')
                    bsps = [bsp]
                if project.game == 'halo1':
                    run_halo1_lightmapper(str(scenario_path), bsps, export_settings)
                else:
                    result = run_lightmapper(
                        False, str(scenario_path), export_settings.lightmap_quality,
                        lightmap_all_bsps=export_settings.lightmap_all_bsps,
                        lightmap_specific_bsp=export_settings.lightmap_specific_bsp,
                        cpu_threads=export_settings.lightmap_threads, structure_bsps=bsps,
                    )
                    if result.lightmap_failed:
                        raise ExportCancelled(result.lightmap_message)
            for warning in export.warnings[warnings_before_tags:]:
                utils.print_warning(warning)
        finally:
            os.chdir(export.original_cwd)
    return export
