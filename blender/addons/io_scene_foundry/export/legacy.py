"""JMS/ASS backend for Foundry's prepared VirtualScene.

The normal export path owns evaluation, filtering, triangulation, face overrides,
animation sampling and restoration. This adapter only converts that result into
the reusable legacy format models and writes files below the data asset folder.
"""
from collections import defaultdict
from copy import copy
from datetime import datetime
from getpass import getuser
from hashlib import sha1
from math import degrees
from pathlib import Path
from tempfile import NamedTemporaryFile
import io
import os
import re
import subprocess
import xml.etree.ElementTree as ET

import bpy
from blam_tags import RealRgbColor
from mathutils import Matrix, Quaternion, Vector

from .process import ExportScene
from .legacy_materials import material_variant
from .cleanup import ANIMATION_EXTENSIONS, prune_intermediates
from .shader_collections import ShaderCollections
from ..legacy import jms_format as jms
from ..legacy import ass_format as ass
from ..legacy.mirror import mirror_ass, mirror_jms, mirror_transform
from ..legacy.writers import VERSIONS, TextWriter, hierarchy, legacy_bone_order, node_checksum, write_jms, write_ass
from ..tags.backend import TagDocument
from ..tags.animation_graph import AnimationGraphTag
from ..tags.model_blender import ModelTag
from ..tags.object import ObjectDocument
from ..tags.scenario import ScenarioDocument
from ..tools.scenario.lightmap import run_halo1_lightmapper
from .. import utils


def legacy_instance_name(name: str, props: dict, mesh_type: int) -> str:
    """Encode pre-Reach instanced-geometry policies in the ASS instance name."""
    prefix = {4: '%', 5: '@', 6: '$', 11: '%'}.get(mesh_type, '')
    base_name = name.lstrip('%@$')
    if mesh_type != 4:
        return prefix + base_name

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
        raise ValueError(f'Invalid legacy export filename: {name!r}')
    return name


def jmi_text(version: int, children: list[str]) -> str:
    """Serialize the small manifest consumed by H2 bulk asset importers."""
    if version < 8207:
        raise ValueError(f'JMI is unavailable for JMS version {version}')
    if not children:
        raise ValueError('JMI requires at least one child model')
    return '\n'.join((str(version), str(len(children)), *children, ''))


def transform(matrix, scale=1, inverse_rotation=False):
    rotation = matrix.to_quaternion()
    if inverse_rotation:
        rotation.invert()
    return jms.Transform((rotation.x, rotation.y, rotation.z, rotation.w), tuple(matrix.translation * scale))


def write_outputs(outputs, *, maya_order=False):
    """Serialize and validate the whole batch before replacing any existing file."""
    staged = []
    try:
        for path, asset in outputs:
            path.parent.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n', dir=path.parent,
                                    prefix=path.name + '.', suffix='.tmp', delete=False) as stream:
                temporary = Path(stream.name)
                staged.append((temporary, path))
                if isinstance(asset, jms.JMS):
                    write_jms(asset, stream, maya_order=maya_order)
                elif isinstance(asset, ass.ASS):
                    write_ass(asset, stream)
                else:
                    stream.write(asset)
            if isinstance(asset, jms.JMS):
                jms.JMS.from_file(temporary)
            elif isinstance(asset, ass.ASS):
                ass.ASS.from_file(temporary)
        for temporary, path in staged:
            temporary.replace(path)
            print(f'--- Saved {path}')
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
        unsupported = ({'crate', 'device_terminal', 'giant'} if self.target_game == 'halo1'
                       else {'device_terminal', 'giant'} if self.target_game == 'halo2'
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
        self.jms_version, self.ass_version, self.jma_version = VERSIONS[self.target_game]
        self.shader_collections = ShaderCollections(self.tags_dir, self.target_game)
        self.granny_textures = False
        self.warned_shader_paths = set()
        self.shader_name_cache = {}
        self.halo1_emissive_variants = {}
        self.skipped_legacy_animations = set()

    def export_legacy(self, single_animation=False):
        self.halo1_emissive_variants.clear()
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
            if node.invalid:
                continue
            if node.props.get('bungie_object_type') == 2:
                if (not single_animation and 'markers' in self.export_tag_types and
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
        outputs = []
        if not single_animation:
            if not grouped and ((self.bones and 'skeleton' in self.export_tag_types) or
                                (markers and 'markers' in self.export_tag_types)):
                grouped[('models' if self.target_game == 'halo1' else 'render',
                         'default superhigh' if self.target_game == 'halo1' else 'default')] = []
            structure_names = {key_name for (key_folder, key_name) in grouped
                               if key_folder == 'structure'}
            if len(structure_names) > 1:
                for marker in markers:
                    if (marker.ob.nwo.marker_type == '_connected_geometry_marker_type_game_instance' and
                            marker.region not in structure_names):
                        raise ValueError(
                            f'{marker.name}: assign this tag-reference marker to one of the '
                            f'exported BSPs ({", ".join(sorted(structure_names))})')
            uses_jmi = (self.target_game == 'halo2' and self.asset_type.name in {
                'PARTICLE_MODEL', 'DECORATOR_SET'})
            jmi_children = []
            for (folder, name), nodes in grouped.items():
                use_ass = self.ass_version is not None and (folder == 'structure' or
                    (folder == 'render' and any(n.props.get('bungie_mesh_type') == 11 for n in nodes)))
                lights = tuple(ob for ob, bsp in self.lights.items()
                               if folder == 'structure' and bsp == name)
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
                asset = (self.ass_asset(
                    name, nodes, ass_markers, lights)
                    if use_ass else self.jms_asset(asset_name, nodes, markers, folder))
                if self.mirror:
                    (mirror_ass if use_ass else mirror_jms)(asset)
                if uses_jmi:
                    if folder != 'render' or use_ass:
                        raise ValueError(
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
        for animation in self.virtual_scene.animations:
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
        if self.external_animations:
            self.warnings.append('Legacy export of external animation files is not implemented. Skipping external animations')
        if self.animation_composites:
            self.warnings.append('JMA cannot encode animation composites. Skipping composites')
        if not outputs and single_animation:
            if self.skipped_legacy_animations:
                return False
            raise ValueError('No JMS, ASS or JMA data matched the export selection')
        if len({str(path).casefold() for path, _ in outputs}) != len(outputs):
            raise ValueError('Legacy output names collide; rename the affected BSP, permutation or animation')
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

    def write_tags(self, single_animation=False):
        """Compile legacy model sources, then update object tags natively."""
        supported_asset_types = {'MODEL', 'SKY', 'ANIMATION', 'SINGLE_ANIMATION'}
        if self.target_game in {'halo1', 'halo2'}:
            supported_asset_types.add('SCENARIO')
        if self.target_game == 'halo2':
            supported_asset_types.update({'PARTICLE_MODEL', 'DECORATOR_SET'})
        if self.asset_type.name not in supported_asset_types:
            raise ValueError(
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
            structure_sources = sorted(
                path for path in structure_dir.iterdir()
                if path.is_file() and path.suffix.lower() == structure_extension
            ) if structure_dir.is_dir() else []
            if not structure_sources:
                raise FileNotFoundError(
                    f'No {structure_extension} structure sources were found in {structure_dir}')
            if self.target_game == 'halo1':
                self.ensure_halo1_shaders(
                    structure_sources, 'shader_environment')
            for source in structure_sources:
                error_path = source.with_name(source.stem + '_errors.wrl')
                previous = error_path.stat() if error_path.is_file() else None
                command = (['structure-new-from-ass', source.relative_to(self.data_dir)]
                           if self.target_game == 'halo2' else
                           ['structure', self.asset_path_relative, source.stem])
                try:
                    utils.run_tool(
                        command,
                        event_level=self.export_settings.event_level,
                        force_tool=True,
                    )
                except subprocess.CalledProcessError:
                    # Scene restoration has already finished before write_tags.
                    # Only display diagnostics produced by this Tool invocation.
                    try:
                        current = error_path.stat() if error_path.is_file() else None
                        if current and (previous is None or
                                (current.st_mtime_ns, current.st_size) !=
                                (previous.st_mtime_ns, previous.st_size)):
                            from ..legacy.wrl import import_errors
                            import_errors(error_path, self.context.scene,
                                          self.rotation_correction, self.to_halo_scale)
                    except Exception as error:
                        print(f'Could not import BSP error geometry: {error}')
                    raise
            self.write_classic_scenario_tag(structure_sources)
            return
        if self.asset_type.name in {'PARTICLE_MODEL', 'DECORATOR_SET'}:
            source = Path(self.asset_path, self.asset_name + '.jmi')
            if not source.is_file():
                raise FileNotFoundError(
                    f'No JMI source was found for {self.asset_type.name.lower()}: '
                    f'{source}')
            command = ('import-particle-model' if self.asset_type.name == 'PARTICLE_MODEL'
                       else 'import-decorator-set')
            utils.run_tool(
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
                raise FileNotFoundError(
                    f'{command} did not create the expected tag: {destination}')
            print(f'--- Wrote {destination}')
            return
        if not animation_only:
            if self.target_game == 'halo1':
                models = Path(self.asset_path, 'models')
                physics = Path(self.asset_path, 'physics')
                model_sources = sorted(models.glob('*.jms')) if models.is_dir() else []
                if model_sources:
                    self.ensure_halo1_shaders(model_sources, 'shader_model')
                    utils.run_tool(['model', self.asset_path_relative],
                                   event_level=self.export_settings.event_level,
                                   **halo1_tool_options)
                if physics.is_dir() and any(physics.glob('*.jms')):
                    for command in ('collision-geometry', 'physics'):
                        utils.run_tool([command, self.asset_path_relative],
                                       event_level=self.export_settings.event_level,
                                       **halo1_tool_options)
            else:
                command = ('bulk-import-model-folder'
                           if self.target_game == 'halo2' or self.export_settings.lightmap_structure
                           else 'bulk-import-model-folder-draft')
                utils.run_tool([command, self.asset_path_relative],
                               event_level=self.export_settings.event_level)

        animation_dir = Path(self.asset_path, 'animations')
        has_animation_sources = (animation_dir.is_dir() and any(
            path.is_file() and path.suffix.lower().startswith('.jm')
            for path in animation_dir.iterdir()))
        import_animations = (single_animation or self.has_blend_animations()) and has_animation_sources
        if import_animations:
            command = 'animations' if self.target_game == 'halo1' else 'model-animations'
            animation_tool_options = dict(halo1_tool_options)
            if self.target_game == 'halo1':
                # H1 asks whether to save the graph after animations have been
                # removed. The output viewer has no interactive stdin.
                animation_tool_options['input_data'] = b'y\n'
            utils.run_tool([command, self.asset_path_relative],
                           event_level=self.export_settings.event_level,
                           **animation_tool_options)
        graph_extension = ('model_animations' if self.target_game == 'halo1'
                           else 'model_animation_graph')
        graph_path = Path(self.tags_dir, self.asset_path_relative,
                          self.asset_name).with_suffix('.' + graph_extension)
        if import_animations or (self.scene_settings.blend_screens_from_blender
                                 and graph_path.is_file()):
            self.write_classic_animation_events()
        if self.target_game == 'halo1' and import_animations:
            self.validate_halo1_animation_skeleton()
        if self.asset_type.name in {'MODEL', 'SKY'}:
            self.write_object_tags()

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
                raise ValueError(
                    'H1 model and animation node order differs. Export geometry and '
                    'all animations together with the same sorting settings; '
                    'rebuild intermediate files before using Tags Only.')
            checksum = model.value(model.tag.root(), 'node list checksum')
            count = len(model.block(model.tag.root(), 'nodes'))
            for animation in graph.block(graph.tag.root(), 'animations'):
                if (graph.value(animation, 'node list checksum') != checksum or
                        graph.value(animation, 'node count') != count):
                    raise ValueError(
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

    def ensure_halo1_shaders(self, source_paths: list[Path], shader_type: str) -> None:
        """Localize referenced H1 shaders before Tool resolves JMS material names."""
        if self.target_game != 'halo1':
            return
        shader_root = Path(self.tags_dir, self.asset_path_relative)
        materials = {}
        for ob in self.ob_halo_data:
            for slot in getattr(ob, 'material_slots', ()):
                mat = slot.material
                if mat is None or not mat.nwo.shader_path.strip():
                    continue
                path = Path(self.tags_dir, utils.relative_path(mat.nwo.shader_path))
                try:
                    key = filename(path.stem).casefold()
                except ValueError:
                    self.warnings.append(f'{mat.name}: invalid Halo 1 shader path {mat.nwo.shader_path}. Using a default shader')
                    continue
                materials.setdefault(key, {})[mat.name] = (mat, path)
        existing = {
            path.stem.casefold()
            for path in shader_root.rglob('*')
            if path.is_file() and path.suffix.lower().startswith('.shader')
        } if shader_root.is_dir() else set()
        for source in source_paths:
            for material in jms.JMS.from_file(source).materials:
                # H1 Tool does not treat the later precise-position `)`
                # marker as a material suffix, so preserve it in the lookup name.
                name = re.sub(
                    r'\b(?:lm|lp|hl|ds|pf|lt|to|at|ro):\S+',
                    '',
                    material.name,
                ).strip().rstrip("%#?!@*$^-&=.;><|~({]}[' ")
                if not name or name.startswith('+'):
                    continue
                name = filename(name)
                if name.casefold() in self.halo1_emissive_variants:
                    source_path, power, color = self.halo1_emissive_variants[name.casefold()]
                    source_valid = (source_path is not None and source_path.is_file()
                                    and source_path.suffix.lower().startswith('.shader'))
                    suffix = source_path.suffix if source_valid else '.' + shader_type
                    destination = shader_root / 'shaders' / (name + suffix)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    if source_valid:
                        utils.copy_file(source_path, destination)
                    else:
                        # The normal H1 path also creates a default shader when
                        # the Blender material has no usable shader tag.
                        if source_path is not None:
                            self.warnings.append(f'{name}: missing Halo 1 shader {source_path}. Using a default shader')
                        destination.unlink(missing_ok=True)
                        with TagDocument(destination, tags_root=self.tags_dir, game='halo1'):
                            pass
                    with TagDocument(destination, tags_root=self.tags_dir, game='halo1', must_exist=True) as shader:
                        radiosity = shader.required_field(shader.tag.root(), 'radiosity').as_struct()
                        if radiosity is None:
                            raise ValueError(f'{destination}: shader has no radiosity struct')
                        shader.required_field(radiosity, 'power').set(power)
                        shader.required_field(radiosity, 'color of emitted light').set(RealRgbColor(*color))
                        shader.tag_has_changes = True
                    for old in destination.parent.iterdir():
                        if (old.is_file() and old.stem.casefold() == name.casefold()
                                and old.suffix.lower().startswith('.shader')
                                and old.resolve() != destination.resolve()):
                            backup = old.with_name(old.name + '.foundry-backup')
                            index = 1
                            while backup.exists():
                                backup = old.with_name(old.name + f'.foundry-backup-{index}')
                                index += 1
                            old.rename(backup)
                    existing.add(name.casefold())
                    print(f'--- Wrote emissive shader {destination}')
                    continue
                candidates = list(materials.get(name.casefold(), {}).values())
                if candidates:
                    paths = {path.resolve() for _, path in candidates}
                    shader_source = candidates[0][1]
                    if (len(paths) != 1 or not shader_source.is_file()
                            or not shader_source.suffix.lower().startswith('.shader')
                            or not shader_source.resolve().is_relative_to(Path(self.tags_dir).resolve())):
                        self.warnings.append(f'{name}: invalid or conflicting Halo 1 shader path. Using an asset shader')
                    else:
                        destination = shader_root / 'shaders' / (name + shader_source.suffix)
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        if shader_source.resolve() != destination.resolve():
                            utils.copy_file(shader_source, destination)
                        # A previous blank shader may have a different class. Keep
                        # a backup, but remove it from Tool's shader-name search.
                        for old in destination.parent.iterdir():
                            if (old.is_file() and old.stem.casefold() == name.casefold()
                                    and old.suffix.lower().startswith('.shader')
                                    and old.resolve() != destination.resolve()):
                                backup = old.with_name(old.name + '.foundry-backup')
                                index = 1
                                while backup.exists():
                                    backup = old.with_name(old.name + f'.foundry-backup-{index}')
                                    index += 1
                                old.rename(backup)
                        for mat, _ in candidates:
                            mat.nwo.shader_path = utils.relative_path(destination)
                        materials[name.casefold()] = {
                            mat.name: (mat, destination) for mat, _ in candidates}
                        existing.add(name.casefold())
                        print(f'--- Copied shader {destination}')
                        continue
                if name.casefold() in existing:
                    if candidates:
                        fallback = next((path for path in shader_root.rglob('*')
                                         if path.is_file() and path.stem.casefold() == name.casefold()
                                         and path.suffix.lower().startswith('.shader')), None)
                        if fallback is not None:
                            for mat, _ in candidates:
                                mat.nwo.shader_path = utils.relative_path(fallback)
                    continue
                destination = Path(
                    shader_root, 'shaders', name + '.' + shader_type
                )
                with TagDocument(
                    destination,
                    tags_root=self.tags_dir,
                    game='halo1',
                ):
                    pass
                existing.add(name.casefold())
                for mat, _ in candidates:
                    mat.nwo.shader_path = utils.relative_path(destination)
                print(f'--- Created {destination}')

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
                    raise FileNotFoundError(f'Asset component tag does not exist: {destination}')
                result[field] = utils.relative_path(destination)
            else:
                result[field] = inherited.get(field)
        return result

    def write_object_tags(self):
        """Create selected high-level object tags through blam-tags."""
        model_path = Path(self.tags_dir, self.asset_path_relative,
                          self.asset_name).with_suffix(
                              '.gbxmodel' if self.target_game == 'halo1' else '.model')
        if self.target_game != 'halo1' and not model_path.is_file():
            raise FileNotFoundError(
                f'Model compilation did not create the expected tag: {model_path}')

        if self.target_game in {'halo2', 'halo3', 'halo3odst'}:
            with ModelTag(path=model_path) as model:
                model.set_asset_paths(preserve_missing=True)
            print(f'--- Wrote model tag paths to {model_path}')

        if (self.asset_type.name == 'SKY'
                and self.target_game in {'halo1', 'halo2'}):
            self.write_classic_sky_tag(model_path)
            return

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

    def write_classic_scenario_tag(self, structure_sources: list[Path]) -> None:
        """Create/update an H1/H2 scenario with its compiled BSP references."""
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
                raise FileNotFoundError(
                    f'Structure compilation did not create the expected tag: {bsp}')
            bsp_paths.append(Path(utils.relative_path(bsp)))

        with ScenarioDocument(
            destination, tags_root=self.tags_dir, game=self.target_game
        ) as scenario:
            scenario.ensure_structure_bsps(bsp_paths)
            if is_new:
                scenario.create_default_profile()
                scenario.set_scenario_type(self.scene_settings.scenario_type)
        print(f'--- Wrote {destination}')

    def write_classic_sky_tag(self, model_path: Path) -> None:
        """Create/update the distinct H1/H2 sky tag reference layout."""
        destination = model_path.with_suffix('.sky')
        with TagDocument(destination, tags_root=self.tags_dir,
                         game=self.target_game) as tag:
            root = tag.tag.root()
            if self.target_game == 'halo1':
                tag.set_reference(root, 'model', utils.relative_path(model_path))
                animation = model_path.with_suffix('.model_animations')
            else:
                render_model = model_path.with_suffix('.render_model')
                if not render_model.is_file():
                    raise FileNotFoundError(
                        f'Sky compilation did not create the expected tag: {render_model}')
                tag.set_reference(root, 'render model',
                                  utils.relative_path(render_model))
                animation = model_path.with_suffix('.model_animation_graph')
            if animation.is_file():
                tag.set_reference(root, 'animation graph',
                                  utils.relative_path(animation))
        print(f'--- Wrote {destination}')

    def write_classic_animation_events(self) -> None:
        """Apply Blender metadata after Tool creates the classic animation tag."""
        extension = ('model_animations' if self.target_game == 'halo1'
                     else 'model_animation_graph')
        destination = Path(
            self.tags_dir, self.asset_path_relative, self.asset_name
        ).with_suffix('.' + extension)
        if not destination.is_file():
            raise FileNotFoundError(
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
                screen_count = graph.blend_screens_from_blender(
                    self.scene_settings.blend_screens,
                    self.scene_settings.animations,
                )
        if animations:
            print(f'--- Updated inline events for {count} animation(s) in {destination}')
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
            self.warnings.append(
                f'{animation.name}: classic animation tags cannot store event types: '
                + ', '.join(sorted(set(unsupported))) + '. Skipping unsupported events')
        # JMA has no event channel. Frame events are written into the compiled
        # tag after Tool finishes, using the original Blender animation data.
        return [], []

    def legacy_shader_name(self, mat):
        path = mat.shader_path
        if not path or not path.strip() or path in {'override', 'shaders\\invalid'}:
            return mat.name
        if path in self.shader_name_cache:
            return self.shader_name_cache[path]
        try:
            name = self.shader_collections.material_name(path)
        except ValueError as exc:
            if path not in self.warned_shader_paths:
                self.warnings.append(f'{mat.name}: {exc}. Using material name')
                self.warned_shader_paths.add(path)
            return mat.name
        if self.target_game == 'halo1':
            try:
                filename(name)
            except ValueError:
                if path not in self.warned_shader_paths:
                    self.warnings.append(f'{mat.name}: invalid Halo 1 shader path {path}. Using material name')
                    self.warned_shader_paths.add(path)
                return mat.name
        source = Path(self.tags_dir, utils.relative_path(path))
        if self.target_game == 'halo2' and not source.suffix:
            source = source.with_suffix('.shader')
        invalid_source = (not source.is_file()
                          or not source.resolve().is_relative_to(Path(self.tags_dir).resolve())
                          or not source.suffix.lower().startswith('.shader'))
        if invalid_source and path not in self.warned_shader_paths:
            self.warnings.append(f'{mat.name}: shader path is invalid or missing: {path}')
            self.warned_shader_paths.add(path)
        self.shader_name_cache[path] = name
        return name

    def halo1_emissive_shader_name(self, mat, shader: str, props: dict) -> str:
        """Allocate a stable H1 shader name for one face emission setting."""
        if 'bungie_lighting_emissive_power' not in props:
            return shader
        power = max(0.0, float(props['bungie_lighting_emissive_power']))
        argb = props.get('bungie_lighting_emissive_color', (255, 255, 255, 255))
        color = tuple(max(0.0, min(1.0, float(channel) / 255.0)) for channel in argb[1:4])
        source = Path(self.tags_dir, utils.relative_path(mat.shader_path)) if mat.shader_path else None
        if source is not None and not source.resolve().is_relative_to(Path(self.tags_dir).resolve()):
            raise ValueError(f'{mat.name}: shader path is outside the tags directory')
        identity = '|'.join((str(source).casefold() if source else shader.casefold(),
                             f'{power:.9g}', *(f'{v:.9g}' for v in color)))
        name = f'f_{shader[:10]}_{sha1(identity.encode("utf-8")).hexdigest()[:12]}'
        self.halo1_emissive_variants[name.casefold()] = (source, power, color)
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
        for mat, _, (start, count) in mesh.groups:
            for face in range(int(start), int(start + count)):
                props = dict(node.props)
                for key, face_set in mesh.face_properties.items():
                    value = face_set.array[face]
                    props[key] = value.tolist() if hasattr(value, 'tolist') else value
                region = props.get('bungie_face_region', node.region or 'default')
                if not isinstance(region, str):
                    region = regions[region]
                gm = props.get('bungie_face_global_material', props.get('bungie_mesh_global_material', 'default'))
                if not isinstance(gm, str):
                    gm = globals_[gm]
                if self.supports_bsp:
                    gm = 'default'  # Pre-H4 BSP surface types are resolved from shaders.
                shader = self.legacy_shader_name(mat)
                if self.target_game == 'halo1' and self.supports_bsp:
                    shader = self.halo1_emissive_shader_name(mat, shader, props)
                name, lighting = material_variant(shader, props, gm,
                    asset.version if isinstance(asset, ass.ASS) else None,
                    self.target_game)
                if props.get('foundry_weather_polyhedron'):
                    name = '+weatherpoly' if self.target_game == 'halo1' else '+weather'
                if node.tag_type in {'collision', 'physics'}:
                    name = gm  # Physics/collision material names are surface types, not display shaders.
                permutation = node.permutation or 'default'
                lod = (node.ob.nwo.mesh_lod
                       if self.target_game == 'halo2' and node.tag_type == 'render'
                       else '')
                definition = f'{permutation} {region}' + (f' {lod}' if lod else '')
                key = (name, definition, lighting)
                if key not in cache:
                    cache[key] = len(asset.materials)
                    asset.materials.append(ass.Material(name, definition, lighting) if isinstance(asset, ass.ASS)
                                           else jms.Material(name, definition, region, permutation, lod.lower()))
                materials[face] = cache[key], region
        return materials

    def vertices(self, node, matrix, weighted=True, implied_root=False):
        mesh = node.mesh
        normal_matrix = matrix.to_3x3().inverted().transposed()
        vertices = []
        for i, position in enumerate(mesh.positions):
            influences = []
            if weighted and mesh.bone_weights is not None:
                for index, weight in zip(mesh.bone_indices[i], mesh.bone_weights[i]):
                    if weight:
                        name = mesh.bone_bindings[int(index)]
                        if name not in self.bone_index:
                            raise ValueError(f'{node.name}: unknown skin bone {name}')
                        influences.append((self.bone_index[name], float(weight)))
                total = sum(w for _, w in influences)
                influences = [(b, w / total) for b, w in influences]
            elif weighted and (self.bones or implied_root):
                influences = [(self.parent_index(node, implied_root), 1)]
            normal = normal_matrix @ Vector(mesh.normals[i] if mesh.normals is not None else (0, 0, 1))
            normal.normalize()
            color = tuple(float(c) for c in mesh.vertex_colors[0][i][:3]) if mesh.vertex_colors else None
            texcoords = tuple(tuple(float(c) for c in uv[i][:2]) for uv in mesh.texcoords)
            if self.target_game in {'halo1', 'halo2'}:
                # VirtualMesh flips V for Granny. H1 and H2 JMS expect
                # Blender's original UV orientation.
                texcoords = tuple((u, 1.0 - v) for u, v in texcoords)
            vertices.append(jms.Vertex(tuple((matrix @ Vector(position)) * self.to_halo_scale), tuple(normal),
                tuple(influences), texcoords, color))
        return vertices

    def xref_record(self, node) -> tuple[str, str, int]:
        """Return the legacy XREF path, object name and signed identifier."""
        source = getattr(node.ob, 'ob', node.ob)
        get = getattr(source, 'get', lambda _name, default=None: default)
        imported_path = str(get('jms_xref_path', '') or
                            get('ass_xref_path', '') or '')
        tag_path = str(node.props.get('bungie_marker_game_instance_tag_name', '') or
                       node.ob.nwo.marker_game_instance_tag_name or '')
        if not imported_path and not tag_path:
            raise ValueError(f'{node.name}: tag-reference marker has no tag path')
        if imported_path:
            path = imported_path.replace('/', '\\')
            default_name = Path(path.replace('\\', '/')).stem
        else:
            relative = Path(tag_path.replace('\\', '/'))
            if relative.is_absolute():
                try:
                    relative = relative.relative_to(self.tags_dir)
                except ValueError:
                    raise ValueError(
                        f'{node.name}: tag-reference path is outside this project: '
                        f'{tag_path}') from None
            elif relative.parts and relative.parts[0].casefold() == 'tags':
                relative = Path(*relative.parts[1:])
            default_name = relative.stem
            asset_dir = relative.parent
            if asset_dir.name.casefold() != default_name.casefold():
                asset_dir /= default_name
            # H2 Tool derives the referenced tag from the source-model path and
            # object name. Match the paths written by the H2 Max exporter even
            # when the original source file is no longer present.
            path = str(Path(self.data_dir, asset_dir, 'render',
                            default_name + '.max'))
        xref_name = str(get('jms_xref_name', '') or get('ass_xref_name', '') or
                        default_name)
        raw_identifier = get('jms_identifier', '')
        try:
            identifier = int(raw_identifier)
        except (TypeError, ValueError):
            identity = str(node.props.get('bungie_object_ID', '') or
                           f'{node.name}\0{path}\0{xref_name}')
            identifier = utils.id_from_string(identity)
        return path, xref_name, identifier

    def jms_asset(self, name, nodes, markers, folder):
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
            materials = self.face_materials(node, asset, cache)
            if folder == 'physics' and self.jms_version >= 8206:
                if len({m[0] for m in materials.values()}) > 1:
                    raise ValueError(f'{node.name}: split physics shapes with different collision materials into separate objects')
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
                        raise ValueError(
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
            asset.vertices.extend(self.vertices(
                node, node.matrix_world, implied_root=True))
            for face, triangle in enumerate(node.mesh.indices.reshape((-1, 3))):
                material, region = materials[face]
                if region not in asset.regions:
                    asset.regions.append(region)
                indices = tuple(int(i) + offset for i in triangle)
                if node.negative_scaling:
                    indices = indices[0], indices[2], indices[1]
                asset.triangles.append(jms.Triangle(material, indices, asset.regions.index(region)))
        if folder == 'physics' and self.jms_version >= 8206:
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
                    raise ValueError(
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
                        limits += (0.0,)  # H3/ODST ragdolls add friction.
                asset.constraints.append(jms.Constraint(
                    kind, node.name.lstrip('$'), parent, child,
                    transform(parent_matrix, self.to_halo_scale),
                    transform(child_matrix, self.to_halo_scale), limits))
        if folder in {'render', 'models'} and 'markers' in self.export_tag_types:
            xref_indices = {}
            for node in markers:
                nwo = node.ob.nwo
                permutations = {p.name for p in nwo.marker_permutations}
                if nwo.marker_uses_regions and permutations:
                    if (name in permutations) == (nwo.marker_permutation_type == 'exclude'):
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
                if region not in asset.regions:
                    asset.regions.append(region)
                marker_name = f'({name} {region}){node.name}' if nwo.marker_uses_regions and self.jms_version >= 8205 else node.name
                asset.markers.append(jms.Marker(marker_name, asset.regions.index(region) if nwo.marker_uses_regions else -1,
                    parent, transform(matrix, self.to_halo_scale), node.props.get('bungie_mesh_primitive_sphere_radius', 1)))
        if self.asset_type.name in {'PARTICLE_MODEL', 'DECORATOR_SET'}:
            asset_label = self.asset_type.name.lower().replace('_', '-')
            vertex_bones = []
            for vertex in asset.vertices:
                influences = [bone for bone, weight in vertex.influences
                              if bone >= 0 and weight > 0.0]
                if len(influences) != 1:
                    raise ValueError(
                        f'H2 {asset_label} geometry must be rigid; each vertex '
                        'must have exactly one bone influence')
                vertex_bones.append(influences[0])
            section_bones = defaultdict(set)
            for triangle in asset.triangles:
                section_bones[(triangle.region, triangle.material)].update(
                    vertex_bones[index] for index in triangle.vertices)
            if any(len(bones) != 1 for bones in section_bones.values()):
                raise ValueError(
                    f'H2 {asset_label} geometry must be rigid; each material '
                    'section must use one bone')
        return asset

    def ass_asset(self, name, nodes, markers=(), lights=()):
        asset = ass.ASS(name=name, version=self.ass_version)
        cache, geometries = {}, {}
        node_instances = {}
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
        for node in ordered_nodes:
            materials = self.face_materials(node, asset, cache)
            matrix = (Matrix.Identity(4) if node.proxy_parent is not None
                      else node.matrix_world)
            loc, rot, scale = matrix.decompose()
            uniform = max(scale) - min(scale) < 1e-5 and min(scale) > 0
            rebuilt = Matrix.LocRotScale(loc, rot, scale)
            uniform = uniform and max(abs(matrix[r][c] - rebuilt[r][c]) for r in range(4) for c in range(4)) < 1e-5
            local = ass.Transform((rot.x, rot.y, rot.z, rot.w), tuple(loc * self.to_halo_scale), tuple(scale)) if uniform else ass.Transform()
            key = (id(node.mesh), tuple(m[0] for m in materials.values()), node.negative_scaling)
            geometry_index = geometries.get(key) if uniform else None
            if geometry_index is None:
                geometry = ass.Geometry('MESH')
                geometry.vertices = self.vertices(node, Matrix.Identity(4) if uniform else matrix, bool(self.bones))
                palette = sorted({b for vertex in geometry.vertices for b, _ in vertex.influences})
                palette_map = {b: i for i, b in enumerate(palette)}
                for vertex in geometry.vertices:
                    vertex.influences = tuple((palette_map[b], weight) for b, weight in vertex.influences)
                geometry.node_indices = list(range(len(palette)))
                for face, triangle in enumerate(node.mesh.indices.reshape((-1, 3))):
                    indices = tuple(int(i) for i in triangle)
                    if node.negative_scaling:
                        indices = indices[0], indices[2], indices[1]
                    geometry.triangles.append(jms.Triangle(materials[face][0], indices))
                geometry_index = len(asset.geometries)
                asset.geometries.append(geometry)
                if uniform:
                    geometries[key] = geometry_index
                geometry_bones = tuple(b + 1 for b in palette)
            else:
                geometry_bones = next(i.bones for i in asset.instances if i.geometry == geometry_index)
            mesh_type = node.props.get('bungie_mesh_type')
            instance_name = legacy_instance_name(node.name, node.props, mesh_type)
            if node.props.get('foundry_weather_polyhedron'):
                if not instance_name.casefold().startswith('+weather'):
                    suffix = instance_name.rpartition(':')[2].lstrip('+')
                    instance_name = '+weather_' + (suffix or str(len(asset.instances)))
            parent = node_instances.get(id(node.proxy_parent), 0)
            if node.proxy_parent is not None:
                # Proxy vertex data is authored in the owning instance's local
                # space. Its ASS child transform must therefore be identity.
                local = ass.Transform()
            instance_index = len(asset.instances)
            asset.instances.append(ass.Instance(geometry_index, instance_name, instance_index,
                parent, 0, local, ass.Transform(), geometry_bones))
            node_instances[id(node)] = instance_index
        if 'markers' in self.export_tag_types:
            xref_geometries = {}
            for node in markers:
                nwo = node.ob.nwo
                permutations = {p.name for p in nwo.marker_permutations}
                if nwo.marker_uses_regions and permutations and (name in permutations) == (nwo.marker_permutation_type == 'exclude'):
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
                        asset.geometries.append(ass.Geometry(
                            'MESH', xref_path=path, xref_name=xref_name))
                    value = transform(node.matrix_world, self.to_halo_scale)
                    asset.instances.append(ass.Instance(
                        geometry_index, node.name, identifier, 0, 0,
                        ass.Transform(value.rotation, value.translation), ass.Transform()))
                    continue
                parent = self.parent_index(node)
                matrix = node.matrix_world
                if parent != -1:
                    matrix = self.bones[parent].matrix_world.inverted() @ matrix
                value = transform(matrix, self.to_halo_scale)
                marker_name = f'#({name} {node.region}){node.name}' if nwo.marker_uses_regions else '#' + node.name
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
        return asset

    @staticmethod
    def animation_extension(animation):
        if animation.overlay:
            return '.jmo'
        if animation.animation_type == 'replacement':
            return '.jmr'
        return {'none': '.jmm', 'xy': '.jma', 'xyyaw': '.jmt', 'xyzyaw': '.jmz'}.get(animation.movement, '.jma')

    def legacy_node_checksum(self, nodes):
        if not self.export_settings.legacy_generate_checksum:
            return self.export_settings.legacy_file_checksum
        return node_checksum(
            nodes, halo1=self.target_game == 'halo1',
            maya_order=self.export_settings.legacy_maya_order)

    def jma_text(self, animation):
        tracks = {name: (positions, rotations, scales) for name, positions, rotations, scales in animation.legacy_tracks}
        if not self.bones or set(self.bone_index) - tracks.keys():
            raise ValueError(f'{animation.name}: animation and exported skeleton do not match')
        stream = io.StringIO()
        w = TextWriter(stream, decimal_places=6 if self.target_game == 'halo1' else None)
        nodes = hierarchy([jms.Node(b.name, self.bone_parents[b.name], jms.Transform((0, 0, 0, 1), (0, 0, 0))) for b in self.bones], halo1=self.target_game == 'halo1', maya_order=self.export_settings.legacy_maya_order)
        w.line(self.jma_version)
        if self.jma_version >= 16394:
            w.line(self.legacy_node_checksum(nodes))
        for value in (animation.frame_count, round(1 / self.virtual_scene.time_step), 1, self.asset_name, len(self.bones)):
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
            for bone in self.bones:
                positions, rotations, scales = tracks[bone.name]
                scale = [scales[frame * 9 + i] for i in (0, 4, 8)]
                if max(scale) - min(scale) > 1e-5:
                    raise ValueError(f'{animation.name}: JMA cannot represent nonuniform scale on {bone.name}')
                x, y, z, q = rotations[frame * 4:frame * 4 + 4]
                matrix = Matrix.LocRotScale(Vector(positions[frame * 3:frame * 3 + 3]), Quaternion((q, x, y, z)), Vector(scale))
                parent = self.bone_parents[bone.name]
                world[bone.name] = world[self.bones[parent].name] @ matrix if parent != -1 else matrix
                if self.jma_version >= 16394:
                    matrix = world[bone.name]
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


def export_legacy_asset(context, asset_name, asset_path, scene_settings, export_settings, single_animation, collection_view_layer=None):
    project = utils.get_project(scene_settings.scene_project)
    if not project or project.game not in VERSIONS:
        raise ValueError('JMS/ASS export requires an H1, H2, H3 or ODST project')
    if scene_settings.asset_type not in {'model', 'sky', 'scenario', 'prefab', 'particle_model', 'decorator_set', 'animation', 'single_animation', 'multi_model', 'multi_prefab'}:
        raise ValueError(f'JMS/ASS export does not support {scene_settings.asset_type} assets')
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
        raise ValueError('Legacy exports must be inside an asset folder below the project data directory')
    ensure_asset_marker(path, data, scene_settings)
    export = LegacyExportScene(context, '', '', scene_settings.asset_type, asset_name, str(path), False,
                               export_settings, scene_settings, context.scene)
    export.new_scene('default')
    try:
        export.ready_scene(collection_view_layer)
        export.get_initial_export_objects()
        export.map_halo_properties()
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
            elif (scene_settings.asset_type == 'scenario' and
                  export_settings.lightmap_structure):
                scenario_path = Path(export.asset_path_relative, export.asset_name)
                scenario_tag = Path(export.tags_dir, scenario_path).with_suffix('.scenario')
                with ScenarioDocument(scenario_tag, tags_root=export.tags_dir,
                                      game='halo1') as scenario:
                    block = scenario.block(scenario.tag.root(), 'structure bsps')
                    bsps = [reference.ShortName for entry in block
                            if (reference := scenario.reference(entry, 'structure bsp')) is not None]
                if not export_settings.lightmap_all_bsps:
                    bsp = export_settings.lightmap_specific_bsp
                    if bsp not in bsps:
                        raise ValueError(f'Specified BSP [{bsp}] does not exist in {scenario_tag}')
                    bsps = [bsp]
                run_halo1_lightmapper(str(scenario_path), bsps, export_settings)
            for warning in export.warnings[warnings_before_tags:]:
                utils.print_warning(warning)
        finally:
            os.chdir(export.original_cwd)
